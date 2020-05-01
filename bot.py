import database as db
import telegram as tg
import codeforces as cf
import util
from util import logger
import AnalyseStandingsService
import UpcomingService
import SummarizingService
import standings
import upcoming
import settings
import Chat
import queue, time
from collections import defaultdict

import threading

# chatId -> function
openCommandFunc = {}
# Change emoji after serveral invalid commands in last 5h
invalidComTimes = defaultdict(lambda : queue.Queue())
invalidComTimesLock = threading.Lock()

def invalidCommandCount(chatId):   # how often was 'invalid command' used in last 5h
	with invalidComTimesLock:
		invalidComTimes[chatId].put(time.time())
		while invalidComTimes[chatId].queue[0] < time.time() - 5*60*60:
			invalidComTimes[chatId].get()
		return invalidComTimes[chatId].qsize() - 1

def setOpenCommandFunc(chatId, func):
	global openCommandFunc
	if func is None:
		if chatId in openCommandFunc:
			del openCommandFunc[chatId]
	else:
		openCommandFunc[chatId] = func


#------------------------- Rating request --------------------------------------
def ratingsOfUsers(userNameArr):
	if len(userNameArr) == 0:
		return ("You have no friends 😭\n"
				"Please add your API key in the settings to add codeforces friends automatically or add friends manually with `/add_friend`.")
	userInfos = cf.getUserInfos(userNameArr)
	if userInfos is False or len(userInfos) == 0:
		return "Unknown user in this list"
	res = "```\n"
	maxNameLen = max([len(user['handle']) for user in userInfos])
	userInfos = sorted(userInfos, key= lambda k: k.get('rating', 0), reverse=True)
	for user in userInfos:
		rating = user.get('rating', 0)
		res += util.getUserSmiley(rating) + " " + user['handle'].ljust(maxNameLen) + ': ' + str(rating) + '\n'
	res += "```"
	return res

def handleRatingRequestCont(chat, handle):
	chat.sendMessage(ratingsOfUsers([util.cleanString(handle)]))
	setOpenCommandFunc(chat.chatId, None)

def handleRatingRequest(chat, req):
	setOpenCommandFunc(chat.chatId, handleRatingRequestCont)
	chat.sendMessage("Codeforces handle:")

def handleFriendRatingsRequest(chat, req):
	setOpenCommandFunc(chat.chatId, None)
	chat.sendMessage(ratingsOfUsers(cf.getFriends(chat)))

# ----- Add Friend -----
def handleAddFriendRequestCont(chat, req):
	handle = util.cleanString(req)
	userInfos = cf.getUserInfos([handle])
	if userInfos == False or len(userInfos) == 0 or "handle" not in userInfos[0]:
		chat.sendMessage("👻 No user with this handle! Please try again:")
	else:
		db.addFriends(chat.chatId, [userInfos[0]['handle']])
		rating = userInfos[0].get('rating', 0)
		chat.sendMessage(util.getUserSmiley(rating) + " User `" + userInfos[0]['handle'] + "` with rating " + str(rating) + " added.")
		setOpenCommandFunc(chat.chatId, None)

def handleAddFriendRequest(chat, req):
	setOpenCommandFunc(chat.chatId, handleAddFriendRequestCont)
	chat.sendMessage("Codeforces handle:")

# ----- Remove Friend -----
def handleRemoveFriendRequestCont(chat, req):
	handle = util.cleanString(req)
	userInfos = cf.getUserInfos([handle])
	if userInfos == False or len(userInfos) == 0 or "handle" not in userInfos[0]:
		chat.sendMessage("👻 No user with this handle!")
	else:
		db.deleteFriendOfUser(userInfos[0]['handle'], chat.chatId)
		chat.sendMessage("💀 User `" + userInfos[0]['handle'] + "` was removed from your friends. If this is one of your Codeforces friends, they will be added automatically again in case you added your API-key. If so, just disable notifications for this user in the settings.")
	setOpenCommandFunc(chat.chatId, None)

def handleRemoveFriendRequest(chat, req):
	setOpenCommandFunc(chat.chatId, handleRemoveFriendRequestCont)
	chat.sendMessage("Codeforces handle:")

#------ Start -------------
def handleStart(chat, text):
	setOpenCommandFunc(chat.chatId, settings.handleSetTimezone)
	chat.sendMessage("🔥*Welcome to the Codeforces Live Bot!*🔥\n\n"
	+ "You will receive reminders for upcoming Codeforces Contests. Please tell me your *timezone* so that "
	+ "the contest start time will be displayed correctly. So text me the name of the city you live in, for example "
	+ "'Munich'.")

#-------- HELP ------------
def handleHelp(chat, text):
	chat.sendMessage("🔥*Codeforces Live Bot*🔥\n\n"
	+ "With this bot you can:\n"
	+ "• receive reminders about upcoming _Codeforces_ contest\n"
	+ "• list upcoming _Codeforces_ contest via /upcoming\n"
	+ "• see the current contest standings of your friends via /current\_standings\n"
	+ "• receive notifications if your friends solve tasks - during the contest or in the upsolving\n"
	+ "• look at the leaderboard of your friends via /friend\_ratings\n"
	+ "• get the current rating of a specific user with /rating\n"
	+ "• manage your friends with /add\_friend and /remove\_friend\n"
	+ "• import your Codeforces friends by adding a Codeforces API key in /settings\n"
	+ "• set your time zone and notification setting in /settings\n"
	+ "\nWe use the following ranking system:\n"
	+ "• " + util.getUserSmiley(2400) + ": rating ≥ 2400\n"
	+ "• " + util.getUserSmiley(2100) + ": rating ≥ 2100\n"
	+ "• " + util.getUserSmiley(1900) + ": rating ≥ 1900\n"
	+ "• " + util.getUserSmiley(1600) + ": rating ≥ 1600\n"
	+ "• " + util.getUserSmiley(1400) + ": rating ≥ 1400\n"
	+ "• " + util.getUserSmiley(1200) + ": rating ≥ 1200\n"
	+ "• " + util.getUserSmiley(1199) + ": rating < 1200\n"
	)

# ------ Other --------
def invalidCommand(chat, msg):
	emoji = ["😅", "😬", "😑", "😠", "😡", "🤬"]
	c = invalidCommandCount(chat.chatId)
	chat.sendMessage("Invalid command!" + emoji[min(len(emoji)-1, c)])

def noCommand(chat, msg):
	if chat.chatId in openCommandFunc:
		openCommandFunc[chat.chatId](chat, msg)
	elif int(chat.chatId) >= 0 or msg.startswith("/"):
		invalidCommand(chat, msg)

#-----
def handleMessage(chat, text):
	logger.info("-> " + text + " <- (" + ((chat.handle + ": ") if chat.handle else "") + str(chat.chatId) + ")")
	text = text.replace("@codeforces_live_bot", "")
	text = text.replace("@codeforces_live_testbot", "")
	msgSwitch = {
		"/start": handleStart,
		"/rating": handleRatingRequest,
		"/friend_ratings": handleFriendRatingsRequest,
		"/add_friend": handleAddFriendRequest,
		"/remove_friend": handleRemoveFriendRequest,
		"/settings": settings.handleSettings,
		"/current_standings": standings.sendStandings,
		"/upcoming": upcoming.handleUpcoming,
		"/help": handleHelp
	}
	func = msgSwitch.get(util.cleanString(text), noCommand)
	func(chat, text)

def initContestServices():
	Chat.initChats()
	services = [
		cf.ContestListService(),
		cf.FriendUpdateService(),
		AnalyseStandingsService.AnalyseStandingsService(),
		UpcomingService.UpcomingService(),
		SummarizingService.SummarizingService()
	]
	for service in services:
		service.start()

def startTestingMode():
	tg.testFlag = True
	initContestServices()
	while True:
		msg = input()
		handleMessage(Chat.getChat('0'), msg)

def startTelegramBot():
	initContestServices()
	tg.TelegramUpdateService().start()
	while True:
		msg = input()
		handleMessage(Chat.getChat('0'), msg)
