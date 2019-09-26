import json
import database as db
import telegram as tg
import codeforces as cf
import util
import bot
import Chat

def handleSettings(chat, req):
	buttons = getButtonSettings(chat)
	replyMarkup = {"inline_keyboard": buttons}
	replyMarkup = json.dumps(replyMarkup)
	chat.sendMessage("What do you want to change?", replyMarkup)

def getButtonSettings(chat):
	buttons = [
		[{"text": "Change time zone",												"callback_data": "settings:timezone"}],
		[{"text": "Change your CF handle",									"callback_data": "settings:handle"}],
		[{"text": "Change Codeforces API key",							"callback_data": "settings:apikey"}],
		[{"text": "Change friends & notification settings", "callback_data": "settings:notf"}],
	]
	return buttons

# all button presses
def handleCallbackQuery(callback):
	chat = Chat.getChat(str(callback['message']['chat']['id']))
	data = callback['data']

	if not ":" in data:
		log("Invalid callback data: "+ data)
		return

	pref, data = data.split(":", 1)

	if pref == "settings":
		handleSettingsCallback(chat, data, callback)
	elif pref == "friend_notf":
		handleFriendNotSettingsCallback(chat, data, callback)
	else:
		log("Invalid callback prefix: "+ pref + ", data: "+ data)

def handleSettingsCallback(chat, data, callback):
	funs = {
		"timezone": handleChangeTimezone,
		"handle": handleSetUserHandlePrompt,
		"apikey": handleSetAuthorization,
		"notf": sendFriendSettingsButtons,
	}
	funs[data](chat, "")
	tg.sendAnswerCallback(callback['id'])

#------ Notification Settings------

def getButtons(handle, ratingWatch, contestWatch):
	text1 = handle + " list ["+ ("X" if ratingWatch else " ") + "]"
	text2 = handle + " notify ["+ ("X" if contestWatch else " ") + "]"
	data1 = "friend_notf:" + handle + ";0;" + ("0" if ratingWatch else "1")
	data2 = "friend_notf:" + handle + ";1;" + ("0" if contestWatch else "1")
	return [{"text":text1, "callback_data":data1}, {"text":text2, "callback_data":data2}]

def getButtonRows(chat):
	buttons = []
	friends = cf.getFriendsWithDetails(chat.chatId)
	if friends == None:
		chat.sendMessage("You don't have any friends :(")
		return

	for [handle, ratingWatch, contestWatch] in friends:
		buttons.append(getButtons(handle, ratingWatch == 1, contestWatch == 1))
	return buttons

def sendFriendSettingsButtons(chat, msg):
	buttons = getButtonRows(chat)

	replyMarkup = {"inline_keyboard": buttons}
	replyMarkup = json.dumps(replyMarkup)
	chat.sendMessage("Click the buttons to change the friend settings.", replyMarkup)

def updateButtons(chat, msg):
	buttons = getButtonRows(chat)

	replyMarkup = {"inline_keyboard": buttons}
	replyMarkup = json.dumps(replyMarkup)
	chat.editMessageReplyMarkup(msg['message_id'], replyMarkup)


def handleFriendNotSettingsCallback(chat, data, callback):
	[handle, button, gesetzt] = data.split(';')
	gesetzt = (gesetzt == '1')
	if button == "0":
		notf = "You will" + ("" if gesetzt else " no longer") + " see "+ handle +" on your list."
		db.setFriendSettings(chat.chatId, handle, 'ratingWatch', gesetzt)
	else:
		notf = "You will" + ("" if gesetzt else " no longer") + " receive notifications for "+ handle +"."
		db.setFriendSettings(chat.chatId, handle, 'contestWatch', gesetzt)
	tg.sendAnswerCallback(callback['id'], notf)

	updateButtons(chat, callback['message'])

# ---- Set User Handle ------
def handleSetUserHandlePrompt(chat, msg):
	bot.setOpenCommandFunc(chat.chatId, handleSetUserHandle)
	chat.sendMessage("Please enter your Codeforces handle:")

def handleSetUserHandle(chat, handle):
	handle = util.cleanString(handle)
	userInfos = cf.getUserInfos([handle])
	if userInfos == False:
		chat.sendMessage("No user with this handle! Try again:")
	else:
		bot.setOpenCommandFunc(chat.chatId, None)
		chat.handle = handle
		db.addFriends(chatId, [handle])
		# db.setFriendSettings(chatId, handle, "contestWatch", 0) #no solved notifications for yourself --YES
		chat.sendMessage("Welcome `" + userInfos[0]['handle'] + "`. Your current rating is " +
			str(userInfos[0]['rating']) + ".")
		if chat.apikey is None:
			chat.sendMessage("Do you want import your friends from Codeforces? Then, I need your Codeforces API key.")
			handleSetAuthorization(chat, "")

# ------- Add API KEY -----
def handleAddSecret(chat, secret):
	chat.secret = secret
	bot.setOpenCommandFunc(chat.chatId, None)
	util.log('new secret added for user ' + str(chat.chatId))
	chat.sendMessage("Key added. Your friends are now added.")

def handleAddKey(chat, key):
	chat.apikey = key
	bot.setOpenCommandFunc(chatId, handleAddSecret)
	tg.sendMessage(chatId, "Enter your secret:")

def handleSetAuthorization(chat, req):
	#offenes Request adden
	bot.setOpenCommandFunc(chat.chatId, handleAddKey)
	chat.sendMessage("Go to https://codeforces.com/settings/api and generate a key.\n"
	+ "Then text me two seperate messages - the first one containing the key and the second one containing the secret")

# ------- Time zone -------------
def handleChangeTimezone(chat, text):
	bot.setOpenCommandFunc(chat.chatId, handleSetTimezone)
	chat.sendMessage("Setting up your time zone... Please enter the city you live in:")

def handleSetTimezone(chat, tzstr):
	tzstr = tzstr.lstrip().rstrip()
	tz = util.getTimeZone(req)
	if not tz:
		chat.sendMessage("Name lookup failed. Please use a different city:")
	else:
		bot.setOpenCommandFunc(chat.chatId, None)
		chat.timezone = tz
		chat.sendMessage("Timezone set to '" + tz + "'")
		# if in setup after start, ask for user handle
		if chat.handle is None:
			chat.sendMessage("Now I need *your* handle.")
			handleSetUserHandlePrompt(chat, "")