import UpdateService
import telegram as tg
import codeforces as cf
import util
import database as db
import standings
import random
import Chat

class AnalyseStandingsService (UpdateService.UpdateService):
	def __init__(self):
		UpdateService.UpdateService.__init__(self, 30)
		self._points = {}
		self._notFinal = {}
		self._doTask(True)

	def _notifyTaskSolved(self, handle, task, rejectedAttemptCount, time, official):
		if official:
			msg = "💡* ["+ util.formatSeconds(time) +"]* "
		else:
			msg = "💡 *[UPSOLVING]* "
		msg += "`"+handle + "` has solved task " + task
		if rejectedAttemptCount > 0:
			msg += " *after " + str(rejectedAttemptCount) + " wrong submissions*"
		for chatId in db.getWhoseFriends(handle):
			Chat.getChat(chatId).sendMessage(msg)

	def _notifyTaskTested(self, handle, task, accepted):
		funnyInsults = ["%s faild on system tests for task %s. What a looser.💩",
										"%s should probably look for a different hobby.💁🏻‍♂️ He faild the system tests for task %s.",
										"📉 %s failed the system tests for task %s. *So sad! It's true.*",
										"Div. 3 is near for %s 👋🏻. He failed the system tests for task %s."]
		if accepted:
			msg = "✔️ You got accepted on system tests for task " + task
			chatIds = db.getChatIds(handle)
			for chatId in chatIds:
				Chat.getChat(chatId).sendMessage(msg)
		else:
			if cf.getUserRating(handle) >= 1800:
				insult = funnyInsults[random.randint(0,len(funnyInsults)-1)]
				msg = insult % (handle, task)
			else:
				msg = handle + " failed on system tests for task " + task
			
			for chatId in db.getWhoseFriends(handle):
				Chat.getChat(chatId).sendMessage(msg)

	def _updateStandings(self, contest, chatIds):
		for chatId in chatIds:
			if chatId not in standings.standingsSent:
				standings.standingsSent[chatId] = {}
			if contest in standings.standingsSent[chatId]:
				util.log('update stadings for ' + str(chatId) + '!')
				standings.updateStandingsForChat(contest, chatId, standings.standingsSent[chatId][contest])

	# analyses the standings
	def _doTask(self, firstRead=False):
		friends = db.getAllFriends()
		for c in cf.getCurrentContestsId():
			if c not in self._points:
				self._points[c] = {}
			if c not in self._notFinal:
				self._notFinal[c] = {}
			standings = cf.getStandings(c, friends)
			if standings == False:
				return
			results = standings['rows']
			lastPoints = self._points[c] #{"handle":[0,3], } also handle -> list of tasks with points
			for r in results:
				handle = r["party"]["members"][0]["handle"]
				if handle not in lastPoints:
					lastPoints[handle] = []
				if handle not in self._notFinal[c]:
					self._notFinal[c][handle] = []
				for taski in range(len(r["problemResults"])):
					task = r["problemResults"][taski]
					flag = False
					taskName = standings["problems"][taski]["index"]
					if task["points"] > 0 and taski not in lastPoints[handle]:
						#notify all chats who have this friend
						if not firstRead:
							self._notifyTaskSolved(handle, taskName, task["rejectedAttemptCount"],
									 task["bestSubmissionTimeSeconds"], r["rank"] != 0)
							# now updating every 30sec during contest
							# update only if after contest
							if standings["contest"]['phase'] == 'FINISHED':
								self._updateStandings(c, db.getWhoseFriends(handle, allList=True))
						lastPoints[handle].append(taski)
						flag = True
						if task['type'] == 'PRELIMINARY' and (taski not in self._notFinal[c][handle]):
							util.log('adding non-final task ' + str(taski) + ' for user ' + str(handle))
							self._notFinal[c][handle].append(taski)
					if task['type'] == 'FINAL' and (taski in self._notFinal[c][handle]):
						util.log('finalizing non-final task ' + str(taski) + ' for user ' + str(handle))
						self._notFinal[c][handle].remove(taski)
						self._notifyTaskTested(handle, taskName, task['points'] > 0)
						self._updateStandings(c, db.getWhoseFriends(handle, allList=True))
			if standings["contest"]['phase'] != 'FINISHED':
				self._updateStandings(c, db.getAllChatPartners())
