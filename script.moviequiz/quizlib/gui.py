#
#      Copyright (C) 2012 Tommy Winther
#      http://tommy.winther.nu
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this Program; see the file LICENSE.txt.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#

import threading
import os
import re
import time

import xbmc
import xbmcgui
import datetime

import game
import question
import player
import db
import highscore

import buggalo

from strings import *

# Constants from [xbmc]/xbmc/guilib/Key.h
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10

ACTION_REMOTE0 = 58
ACTION_REMOTE1 = 59
ACTION_REMOTE2 = 60
ACTION_REMOTE3 = 61
ACTION_REMOTE4 = 62
ACTION_REMOTE5 = 63
ACTION_REMOTE6 = 64
ACTION_REMOTE7 = 65
ACTION_REMOTE8 = 66
ACTION_REMOTE9 = 67

ACTION_JUMP_SMS2 = 142
ACTION_JUMP_SMS3 = 143
ACTION_JUMP_SMS4 = 144
ACTION_JUMP_SMS5 = 145
ACTION_JUMP_SMS6 = 146
ACTION_JUMP_SMS7 = 147
ACTION_JUMP_SMS8 = 148
ACTION_JUMP_SMS9 = 149

RESOURCES_PATH = os.path.join(ADDON.getAddonInfo('path'), 'resources', )
AUDIO_CORRECT = os.path.join(RESOURCES_PATH, 'audio', 'correct.wav')
AUDIO_WRONG = os.path.join(RESOURCES_PATH, 'audio', 'wrong.wav')
BACKGROUND_MOVIE = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-movie.jpg')
BACKGROUND_TV = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-background-tvshows.jpg')
NO_PHOTO_IMAGE = os.path.join(RESOURCES_PATH, 'skins', 'Default', 'media', 'quiz-no-photo.png')

MPAA_RATINGS = ['R', 'Rated R', 'PG-13', 'Rated PG-13', 'PG', 'Rated PG', 'G', 'Rated G']
CONTENT_RATINGS = ['TV-MA', 'TV-14', 'TV-PG', 'TV-G', 'TV-Y7-FV', 'TV-Y7', 'TV-Y']

class LoadingGui(xbmcgui.WindowXMLDialog):
    def __new__(cls, menuGui):
        return super(LoadingGui, cls).__new__(cls, 'script-moviequiz-loading.xml', ADDON.getAddonInfo('path'))

    def __init__(self, menuGui):
        super(LoadingGui, self).__init__()
        self.menuGui = menuGui

    @buggalo.buggalo_try_except()
    def onInit(self):
        startTime = datetime.datetime.now()
        self.menuGui.loadTrivia()
        question.IMDB.loadData()

        delta = datetime.datetime.now() - startTime
        if delta.seconds < 2:
            xbmc.sleep(1000 * (2 - delta.seconds))
        self.close()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU]:
            self.close()

    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        pass

    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        pass



class MenuGui(xbmcgui.WindowXML):

    C_MENU_MOVIE_QUIZ = 4001
    C_MENU_TVSHOW_QUIZ = 4002
    C_MENU_ABOUT = 4000
    C_MENU_EXIT = 4003
    C_MENU_COLLECTION_TRIVIA = 6000
    C_MENU_USER_SELECT = 6001

    def __new__(cls):
        return super(MenuGui, cls).__new__(cls, 'script-moviequiz-menu.xml', ADDON.getAddonInfo('path'))

    def __init__(self):
        super(MenuGui, self).__init__()
        self.trivia = None
        self.database = db.Database.connect()

        if self.database is None:
            pass

    def close(self):
        self.database.close()
        super(MenuGui, self).close()

    @buggalo.buggalo_try_except()
    def onInit(self):
        if not self.trivia:
            loadingGui = LoadingGui(self)
            loadingGui.doModal()
            del loadingGui

        # Check preconditions
        if not self.database.hasMovies() and not self.database.hasTVShows():
            # Must have at least one movie or tvshow
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_REQUIREMENTS_MISSING_LINE1),
                strings(E_REQUIREMENTS_MISSING_LINE2), strings(E_REQUIREMENTS_MISSING_LINE3))
            self.close()
            return

        if not self.database.isAnyVideosWatched() and ADDON.getSetting(SETT_ONLY_WATCHED_MOVIES) == 'true':
            # Only watched movies requires at least one watched video files
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_ONLY_WATCHED_LINE1),
                strings(E_ONLY_WATCHED_LINE2), strings(E_ONLY_WATCHED_LINE3))
            ADDON.setSetting(SETT_ONLY_WATCHED_MOVIES, 'false')

        if not self.database.isAnyMPAARatingsAvailable() and ADDON.getSetting(SETT_MOVIE_RATING_LIMIT_ENABLED) == 'true':
            # MPAA rating requires ratings to be available in database
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_MOVIE_RATING_LIMIT_LINE1),
                strings(E_MOVIE_RATING_LIMIT_LINE2), strings(E_MOVIE_RATING_LIMIT_LINE3))
            ADDON.setSetting(SETT_MOVIE_RATING_LIMIT_ENABLED, 'false')

        if not self.database.isAnyContentRatingsAvailable() and ADDON.getSetting(SETT_TVSHOW_RATING_LIMIT_ENABLED) == 'true':
            # Content rating requires ratings to be available in database
            xbmcgui.Dialog().ok(strings(E_REQUIREMENTS_MISSING), strings(E_TVSHOW_RATING_LIMIT_LINE1),
                strings(E_TVSHOW_RATING_LIMIT_LINE2), strings(E_TVSHOW_RATING_LIMIT_LINE3))
            ADDON.setSetting(SETT_TVSHOW_RATING_LIMIT_ENABLED, 'false')

        self.getControl(self.C_MENU_MOVIE_QUIZ).setEnabled(bool(self.database.hasMovies() and question.isAnyMovieQuestionsEnabled()))
        self.getControl(self.C_MENU_TVSHOW_QUIZ).setEnabled(bool(self.database.hasTVShows() and question.isAnyTVShowQuestionsEnabled()))

        label = '  *  '.join(self.trivia)
        self.getControl(self.C_MENU_COLLECTION_TRIVIA).setLabel(label)

        self.onUpdateUserSelectList()

        if not question.isAnyMovieQuestionsEnabled():
            xbmcgui.Dialog().ok(strings(E_WARNING), strings(E_ALL_MOVIE_QUESTIONS_DISABLED), strings(E_QUIZ_TYPE_NOT_AVAILABLE))

        if not question.isAnyTVShowQuestionsEnabled():
            xbmcgui.Dialog().ok(strings(E_WARNING), strings(E_ALL_TVSHOW_QUESTIONS_DISABLED), strings(E_QUIZ_TYPE_NOT_AVAILABLE))

    def loadTrivia(self):
        self.trivia = ['Movie Quiz v.' + ADDON.getAddonInfo('version'),
                       strings(M_DEVELOPED_BY), strings(M_TRANSLATED_BY)]

        if self.database.hasMovies():
            movies = self.database.fetchone('SELECT COUNT(*) AS count, (SUM(c11) / 60) AS total_hours FROM movie')
            actors = self.database.fetchone('SELECT COUNT(DISTINCT idActor) AS count FROM actorlinkmovie')
            directors = self.database.fetchone('SELECT COUNT(DISTINCT idDirector) AS count FROM directorlinkmovie')
            studios = self.database.fetchone('SELECT COUNT(idStudio) AS count FROM studio')

            self.trivia.append(strings(M_MOVIE_COLLECTION_TRIVIA))
            if movies is not None:
                self.trivia.append(strings(M_MOVIE_COUNT) % movies['count'])
            if actors is not None:
                self.trivia.append(strings(M_ACTOR_COUNT) % actors['count'])
            if directors is not None:
                self.trivia.append(strings(M_DIRECTOR_COUNT) % directors['count'])
            if studios is not None:
                self.trivia.append(strings(M_STUDIO_COUNT) % studios['count'])
            if movies is not None:
                self.trivia.append(strings(M_HOURS_OF_ENTERTAINMENT) % int(movies['total_hours']))

        if self.database.hasTVShows():
            shows = self.database.fetchone('SELECT COUNT(*) AS count FROM tvshow')
            seasons = self.database.fetchone('SELECT SUM(season_count) AS count FROM (SELECT idShow, COUNT(DISTINCT c12) AS season_count from episodeview GROUP BY idShow) AS tbl')
            episodes = self.database.fetchone('SELECT COUNT(*) AS count FROM episode')

            self.trivia.append(strings(M_TVSHOW_COLLECTION_TRIVIA))
            if shows is not None:
                self.trivia.append(strings(M_TVSHOW_COUNT) % shows['count'])
            if seasons is not None:
                self.trivia.append(strings(M_SEASON_COUNT) % seasons['count'])
            if episodes is not None:
                self.trivia.append(strings(M_EPISODE_COUNT) % episodes['count'])

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU]:
            self.close()

        listControl = self.getControl(self.C_MENU_USER_SELECT)
        if listControl.getSelectedItem() is not None and listControl.getSelectedItem().getProperty('id') == '-1':
            # A user must be selected before leaving control
            self.getControl(self.C_MENU_MOVIE_QUIZ).setEnabled(False)
            self.getControl(self.C_MENU_TVSHOW_QUIZ).setEnabled(False)
        else:
            self.getControl(self.C_MENU_MOVIE_QUIZ).setEnabled(True)
            self.getControl(self.C_MENU_TVSHOW_QUIZ).setEnabled(True)


    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        """
        @param controlId: id of the control that was clicked
        @type controlId: int
        """
        listControl = self.getControl(self.C_MENU_USER_SELECT)
        item = listControl.getSelectedItem()

        if controlId == self.C_MENU_MOVIE_QUIZ:
            if item is None:
                xbmcgui.Dialog().ok(strings(CHOOSE_PLAYER), strings(CHOOSE_PLAYER_LINE_1))
                return
            w = GameTypeDialog(game.GAMETYPE_MOVIE, item.getProperty('id'))
            w.doModal()
            del w

        elif controlId == self.C_MENU_TVSHOW_QUIZ:
            if item is None:
                xbmcgui.Dialog().ok(strings(CHOOSE_PLAYER), strings(CHOOSE_PLAYER_LINE_1))
                return
            w = GameTypeDialog(game.GAMETYPE_TVSHOW, item.getProperty('id'))
            w.doModal()
            del w

        elif controlId == self.C_MENU_ABOUT:
            w = AboutDialog()
            w.doModal()
            del w

        elif controlId == self.C_MENU_EXIT:
            self.close()

        elif controlId == self.C_MENU_USER_SELECT:
            if item.getProperty('id') == '-1':
                self.onAddNewUser()
                self.onUpdateUserSelectList()

            else:
                deleteUser = xbmcgui.Dialog().yesno(strings(E_DELETE_USER, str(item.getLabel())),
                                                    strings(E_DELETE_USER_LINE1), strings(E_DELETE_USER_LINE2))
                if deleteUser:
                    localHighscore = highscore.LocalHighscoreDatabase(xbmc.translatePath(ADDON.getAddonInfo('profile')))
                    localHighscore.deleteUser(item.getProperty('id'))
                    localHighscore.close()
                    self.onUpdateUserSelectList()



    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        pass

    def onAddNewUser(self, createDefault = False):
        keyboard = xbmc.Keyboard('', strings(G_WELCOME_ENTER_NICKNAME))
        keyboard.doModal()
        name = None
        if keyboard.isConfirmed() and len(keyboard.getText().strip()) > 0:
            name =  keyboard.getText().strip()
        elif createDefault:
            name = 'Unknown player'

        if name is not None:
            localHighscore = highscore.LocalHighscoreDatabase(xbmc.translatePath(ADDON.getAddonInfo('profile')))
            localHighscore.createUser(name)
            localHighscore.close()

    def onUpdateUserSelectList(self):
        localHighscore = highscore.LocalHighscoreDatabase(xbmc.translatePath(ADDON.getAddonInfo('profile')))
        if not localHighscore.getUsers():
            self.onAddNewUser(createDefault = True)

        listControl = self.getControl(self.C_MENU_USER_SELECT)
        listControl.reset()
        for user in localHighscore.getUsers():
            item = xbmcgui.ListItem(user['nickname'])
            item.setProperty('id', str(user['id']))
            listControl.addItem(item)

        item = xbmcgui.ListItem(strings(G_ADD_USER))
        item.setProperty('id', '-1')
        listControl.addItem(item)
        
        localHighscore.close()

class GameTypeDialog(xbmcgui.WindowXMLDialog):
    C_GAMETYPE_VISIBLE_MARKER = 100

    C_GAMETYPE_UNLIMITED = 4000
    C_GAMETYPE_TIME_LIMITED = 4001
    C_GAMETYPE_QUESTION_LIMITED = 4002

    C_GAMETYPE_UNLIMITED_CANCEL = 4003
    C_GAMETYPE_TIME_LIMITED_CANCEL = 4103
    C_GAMETYPE_QUESTION_LIMITED_CANCEL = 4203

    C_GAMETYPE_UNLIMITED_PLAY = 4004
    C_GAMETYPE_TIME_LIMITED_PLAY = 4104
    C_GAMETYPE_QUESTION_LIMITED_PLAY = 4204

    C_GAMETYPE_TIME_LIMIT = 4100
    C_GAMETYPE_TIME_LIMIT_NEXT = 4101
    C_GAMETYPE_TIME_LIMIT_PREVIOUS = 4102

    C_GAMETYPE_QUESTION_LIMIT = 4200
    C_GAMETYPE_QUESTION_LIMIT_NEXT = 4201
    C_GAMETYPE_QUESTION_LIMIT_PREVIOUS = 4202

    QUESTION_SUB_TYPES = [
        {'limit' : '5', 'text' : strings(M_X_QUESTIONS, '5')},
        {'limit' : '10', 'text' : strings(M_X_QUESTIONS, '10')},
        {'limit' : '15', 'text' : strings(M_X_QUESTIONS, '15')},
        {'limit' : '25', 'text' : strings(M_X_QUESTIONS, '25')},
        {'limit' : '50', 'text' : strings(M_X_QUESTIONS, '50')},
        {'limit' : '100', 'text' : strings(M_X_QUESTIONS, '100')}
    ]
    TIME_SUB_TYPES = [
        {'limit' : '1', 'text' : strings(M_ONE_MINUTE)},
        {'limit' : '2', 'text' : strings(M_X_MINUTES, '2')},
        {'limit' : '3', 'text' : strings(M_X_MINUTES, '3')},
        {'limit' : '5', 'text' : strings(M_X_MINUTES, '5')},
        {'limit' : '10', 'text' : strings(M_X_MINUTES, '10')},
        {'limit' : '15', 'text' : strings(M_X_MINUTES, '15')},
        {'limit' : '30', 'text' : strings(M_X_MINUTES, '30')}
    ]

    VISIBLE_UNLIMITED = 'unlimited'
    VISIBLE_TIME_LIMITED = 'time-limited'
    VISIBLE_QUESTION_LIMITED = 'question-limited'

    def __new__(cls, type, userId):
        return super(GameTypeDialog, cls).__new__(cls, 'script-moviequiz-gametype.xml', ADDON.getAddonInfo('path'))

    def __init__(self, type, userId):
        super(GameTypeDialog, self).__init__()
        self.type = type
        self.userId = userId

    @buggalo.buggalo_try_except()
    def onInit(self):
        if self.type == game.GAMETYPE_MOVIE:
            self.getControl(3999).setLabel(strings(M_CHOOSE_MOVIE_GAME_TYPE))
        elif  self.type == game.GAMETYPE_TVSHOW:
            self.getControl(3999).setLabel(strings(M_CHOOSE_TV_GAME_TYPE))

        control = self.getControl(self.C_GAMETYPE_QUESTION_LIMIT)
        for subTypes in self.QUESTION_SUB_TYPES:
            item = xbmcgui.ListItem(subTypes['text'])
            item.setProperty("limit", subTypes['limit'])
            control.addItem(item)

        control = self.getControl(self.C_GAMETYPE_TIME_LIMIT)
        for subTypes in self.TIME_SUB_TYPES:
            item = xbmcgui.ListItem(subTypes['text'])
            item.setProperty("limit", subTypes['limit'])
            control.addItem(item)

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU]:
            self.close()

    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        interactive = True
        gameInstance = None
        if controlId in [self.C_GAMETYPE_UNLIMITED_CANCEL, self.C_GAMETYPE_TIME_LIMITED_CANCEL, self.C_GAMETYPE_QUESTION_LIMITED_CANCEL]:
            self.close()

        elif controlId in [self.C_GAMETYPE_UNLIMITED, self.C_GAMETYPE_UNLIMITED_PLAY]:
            gameInstance = game.UnlimitedGame(self.type, self.userId, interactive)

        elif controlId in [self.C_GAMETYPE_QUESTION_LIMITED, self.C_GAMETYPE_QUESTION_LIMITED_PLAY]:
            control = self.getControl(self.C_GAMETYPE_QUESTION_LIMIT)
            maxQuestions = int(control.getSelectedItem().getProperty("limit"))
            gameInstance = game.QuestionLimitedGame(self.type, self.userId, interactive, maxQuestions)

        elif controlId in [self.C_GAMETYPE_TIME_LIMITED, self.C_GAMETYPE_TIME_LIMITED_PLAY]:
            control = self.getControl(self.C_GAMETYPE_TIME_LIMIT)
            timeLimit = int(control.getSelectedItem().getProperty("limit"))
            gameInstance = game.TimeLimitedGame(self.type, self.userId, interactive, timeLimit)

        elif controlId == self.C_GAMETYPE_TIME_LIMIT_NEXT:
            control = self.getControl(self.C_GAMETYPE_TIME_LIMIT)
            idx = control.getSelectedPosition() + 1
            if idx > len(self.TIME_SUB_TYPES) - 1:
                idx = 0
            control.selectItem(idx)

        elif controlId == self.C_GAMETYPE_TIME_LIMIT_PREVIOUS:
            control = self.getControl(self.C_GAMETYPE_TIME_LIMIT)
            idx = control.getSelectedPosition() - 1
            if idx < 0:
                idx = len(self.TIME_SUB_TYPES) - 1
            control.selectItem(idx)

        elif controlId == self.C_GAMETYPE_QUESTION_LIMIT_NEXT:
            control = self.getControl(self.C_GAMETYPE_QUESTION_LIMIT)
            idx = control.getSelectedPosition() + 1
            if idx > len(self.QUESTION_SUB_TYPES) - 1:
                idx = 0
            control.selectItem(idx)

        elif controlId == self.C_GAMETYPE_QUESTION_LIMIT_PREVIOUS:
            control = self.getControl(self.C_GAMETYPE_QUESTION_LIMIT)
            idx = control.getSelectedPosition() - 1
            if idx < 0:
                idx = len(self.QUESTION_SUB_TYPES) - 1
            control.selectItem(idx)

        if gameInstance is not None:
            self.close()

            w = QuizGui(gameInstance)
            w.doModal()
            del w

    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        if controlId == self.C_GAMETYPE_UNLIMITED:
            self.getControl(self.C_GAMETYPE_VISIBLE_MARKER).setLabel(self.VISIBLE_UNLIMITED)
        elif controlId == self.C_GAMETYPE_QUESTION_LIMITED:
            self.getControl(self.C_GAMETYPE_VISIBLE_MARKER).setLabel(self.VISIBLE_QUESTION_LIMITED)
        elif controlId == self.C_GAMETYPE_TIME_LIMITED:
            self.getControl(self.C_GAMETYPE_VISIBLE_MARKER).setLabel(self.VISIBLE_TIME_LIMITED)


class AboutDialog(xbmcgui.WindowXMLDialog):
    C_ABOUT_VISIBILITY_MARKER = 100
    C_ABOUT_HIGHSCORE_BUTTON = 500
    C_ABOUT_STATISTICS_BUTTON = 501
    C_ABOUT_ABOUT_BUTTON = 502
    C_ABOUT_CHANGELOG_BUTTON = 503
    C_ABOUT_CLOSE_BUTTON = 504

    C_ABOUT_GLOBAL_HIGHSCORE_LIST = 1001
    C_ABOUT_HIGHSCORE_GLOBAL_TOGGLE = 1002
    C_ABOUT_HIGHSCORE_TYPE_LIST = 1003
    C_ABOUT_HIGHSCORE_MOVIE_TOGGLE = 1004

    C_ABOUT_STATISTICS = 2001
    C_ABOUT_STATISTICS_COUNTRIES = 2002
    C_ABOUT_STATISTICS_USERS = 2003
    C_ABOUT_ABOUT = 3001
    C_ABOUT_CHANGELOG = 4001

    VISIBLE_HIGHSCORES = 'highscores'
    VISIBLE_STATISTICS = 'statistics'
    VISIBLE_ABOUT = 'about'
    VISIBLE_CHANGELOG = 'changelog'

    GAME_TYPES = [
        game.UnlimitedGame(game.GAMETYPE_MOVIE, -1, True),

        game.QuestionLimitedGame(game.GAMETYPE_MOVIE, -1, True, 5),
        game.QuestionLimitedGame(game.GAMETYPE_MOVIE, -1, True, 10),
        game.QuestionLimitedGame(game.GAMETYPE_MOVIE, -1, True, 15),
        game.QuestionLimitedGame(game.GAMETYPE_MOVIE, -1, True, 25),
        game.QuestionLimitedGame(game.GAMETYPE_MOVIE, -1, True, 50),
        game.QuestionLimitedGame(game.GAMETYPE_MOVIE, -1, True, 100),

        game.TimeLimitedGame(game.GAMETYPE_MOVIE, -1, True, 1),
        game.TimeLimitedGame(game.GAMETYPE_MOVIE, -1, True, 2),
        game.TimeLimitedGame(game.GAMETYPE_MOVIE, -1, True, 3),
        game.TimeLimitedGame(game.GAMETYPE_MOVIE, -1, True, 5),
        game.TimeLimitedGame(game.GAMETYPE_MOVIE, -1, True, 10),
        game.TimeLimitedGame(game.GAMETYPE_MOVIE, -1, True, 15),
        game.TimeLimitedGame(game.GAMETYPE_MOVIE, -1, True, 30),
    ]

    def __new__(cls):
        return super(AboutDialog, cls).__new__(cls, 'script-moviequiz-about.xml', ADDON.getAddonInfo('path'))

    def __init__(self):
        super(AboutDialog, self).__init__()
        self.globalHighscore = highscore.GlobalHighscoreDatabase(ADDON.getAddonInfo('version'))
        self.localHighscore = highscore.LocalHighscoreDatabase(xbmc.translatePath(ADDON.getAddonInfo('profile')))

        self.useGlobal = True
        self.useMovieQuiz = True
        self.gameType = self.GAME_TYPES[0]
        self.isClosing = False

    def close(self):
        self.localHighscore.close()
        self.isClosing = True
        super(AboutDialog, self).close()

    @buggalo.buggalo_try_except()
    def onInit(self):
        f = open(ADDON.getAddonInfo('changelog'))
        changelog = f.read()
        f.close()
        self.getControl(self.C_ABOUT_CHANGELOG).setText(changelog)

        f = open(os.path.join(ADDON.getAddonInfo('path'), 'about.txt'))
        about = f.read()
        f.close()
        self.getControl(self.C_ABOUT_ABOUT).setText(about)

        self.typeOptionList = []
        for type in self.GAME_TYPES:
            if isinstance(type, game.UnlimitedGame):
                self.typeOptionList.append(strings(M_UNLIMITED))
            elif isinstance(type, game.QuestionLimitedGame):
                self.typeOptionList.append(strings(M_X_QUESTIONS, type.getGameSubType()))
            elif isinstance(type, game.TimeLimitedGame):
                self.typeOptionList.append(strings(M_X_MINUTES, type.getGameSubType()))
            else:
                self.typeOptionList.append(repr(type))

        statistics = self.globalHighscore.getStatistics()
        statisticsLabel = strings(M_STATISTICS, (
                                  statistics['users']['unique_ips'],
                                  statistics['users']['unique_countries'],
                                  statistics['quiz']['total_games'],
                                  statistics['quiz']['total_questions'],
                                  statistics['quiz']['total_correct_answers'],
                                  statistics['quiz']['correct_percentage']
                                  ))
        self.getControl(self.C_ABOUT_STATISTICS).setLabel(statisticsLabel)

        listControl = self.getControl(self.C_ABOUT_STATISTICS_COUNTRIES)
        listControl.reset()
        items = list()
        for entry in statistics['top_countries']:
            item = xbmcgui.ListItem('%s games' % entry['highscores'])
            item.setProperty('countryIconUrl', entry['countryIconUrl'])
            items.append(item)
        listControl.addItems(items)

        listControl = self.getControl(self.C_ABOUT_STATISTICS_USERS)
        listControl.reset()
        items = list()
        for entry in statistics['top_users']:
            item = xbmcgui.ListItem(entry['nickname'])
            item.setProperty('games', '%s games' % entry['games'])
            item.setProperty('countryIconUrl', entry['countryIconUrl'])
            items.append(item)
        listControl.addItems(items)

        self.reloadHighscores()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU]:
            self.close()

    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        if controlId == self.C_ABOUT_CLOSE_BUTTON:
            self.close()

        elif controlId == self.C_ABOUT_HIGHSCORE_GLOBAL_TOGGLE:
            self.useGlobal = not self.useGlobal
            self.reloadHighscores()

        elif controlId == self.C_ABOUT_HIGHSCORE_TYPE_LIST:
            idx = xbmcgui.Dialog().select(strings(M_CHOOSE_TYPE), self.typeOptionList)
            if idx != -1:
                self.getControl(self.C_ABOUT_HIGHSCORE_TYPE_LIST).setLabel(self.typeOptionList[idx])
                self.gameType = self.GAME_TYPES[idx]
                self.reloadHighscores()

        elif controlId == self.C_ABOUT_HIGHSCORE_MOVIE_TOGGLE:
            self.useMovieQuiz = not self.useMovieQuiz
            self.reloadHighscores()

    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        if controlId == self.C_ABOUT_HIGHSCORE_BUTTON:
            self.getControl(self.C_ABOUT_VISIBILITY_MARKER).setLabel(self.VISIBLE_HIGHSCORES)
        elif controlId == self.C_ABOUT_STATISTICS_BUTTON:
            self.getControl(self.C_ABOUT_VISIBILITY_MARKER).setLabel(self.VISIBLE_STATISTICS)
        elif controlId == self.C_ABOUT_ABOUT_BUTTON:
            self.getControl(self.C_ABOUT_VISIBILITY_MARKER).setLabel(self.VISIBLE_ABOUT)
        elif controlId == self.C_ABOUT_CHANGELOG_BUTTON:
            self.getControl(self.C_ABOUT_VISIBILITY_MARKER).setLabel(self.VISIBLE_CHANGELOG)

    def reloadHighscores(self):
        threading.Timer(0.1, self.reloadHighscoresInThread).start()

    @buggalo.buggalo_try_except()
    def reloadHighscoresInThread(self):
        if self.useMovieQuiz:
            self.gameType.setType(game.GAMETYPE_MOVIE)
        else:
            self.gameType.setType(game.GAMETYPE_TVSHOW)

        if self.useGlobal:
            entries = self.globalHighscore.getHighscores(self.gameType)
        else:
            entries = self.localHighscore.getHighscores(self.gameType)

        listControl = self.getControl(self.C_ABOUT_GLOBAL_HIGHSCORE_LIST)
        listControl.reset()
        items = list()
        for idx, entry in enumerate(entries):
            item = xbmcgui.ListItem(entry['nickname'])
            item.setProperty('position', str(entry['position']))
            item.setProperty('score', str(entry['score']))
            if self.useGlobal:
                item.setProperty('countryIconUrl', entry['countryIconUrl'])
                item.setProperty('timestamp', entry['timeAgo'])
            else:
                item.setProperty('timestamp', entry['timestamp'])
            items.append(item)

            if self.isClosing:
                return

        listControl.addItems(items)


class QuizGui(xbmcgui.WindowXML):
    C_MAIN_FIRST_ANSWER = 4000
    C_MAIN_LAST_ANSWER = 4003
    C_MAIN_REPLAY = 4010
    C_MAIN_EXIT = 4011
    C_MAIN_LOADING = 4020
    C_MAIN_CORRECT_SCORE = 4101
    C_MAIN_INCORRECT_SCORE = 4103
    C_MAIN_QUESTION_COUNT = 4104
    C_MAIN_COVER_IMAGE = 4200
    C_MAIN_QUESTION_LABEL = 4300
    C_MAIN_PHOTO = 4400
    C_MAIN_MOVIE_BACKGROUND = 4500
    C_MAIN_TVSHOW_BACKGROUND = 4501
    C_MAIN_QUOTE_LABEL = 4600
    C_MAIN_PHOTO_1 = 4701
    C_MAIN_PHOTO_2 = 4702
    C_MAIN_PHOTO_3 = 4703
    C_MAIN_PHOTO_LABEL_1 = 4711
    C_MAIN_PHOTO_LABEL_2 = 4712
    C_MAIN_PHOTO_LABEL_3 = 4713
    C_MAIN_VIDEO_FILE_NOT_FOUND = 4800
    C_MAIN_VIDEO_VISIBILITY = 5000
    C_MAIN_PHOTO_VISIBILITY = 5001
    C_MAIN_QUOTE_VISIBILITY = 5004
    C_MAIN_THREE_PHOTOS_VISIBILITY = 5006
    C_MAIN_THEME_VISIBILITY = 5008
    C_MAIN_CORRECT_VISIBILITY = 5002
    C_MAIN_INCORRECT_VISIBILITY = 5003
    C_MAIN_LOADING_VISIBILITY = 5005
    C_MAIN_COVER_IMAGE_VISIBILITY = 5007

    STATE_LOADING = 1
    STATE_PLAYING = 2
    STATE_GAME_OVER = 3

    def __new__(cls, gameInstance):
        return super(QuizGui, cls).__new__(cls, 'script-moviequiz-main.xml', ADDON.getAddonInfo('path'))

    def __init__(self, gameInstance):
        """
        @param gameInstance: the Game instance
        @type gameInstance: Game
        """
        super(QuizGui, self).__init__()

        self.gameInstance = gameInstance
        xbmc.log("Starting game: %s" + str(self.gameInstance))

        if self.gameInstance.getType() == game.GAMETYPE_TVSHOW:
            self.defaultBackground = BACKGROUND_TV
        else:
            self.defaultBackground = BACKGROUND_MOVIE

        ratings = None
        if gameInstance.getType() == game.GAMETYPE_MOVIE and ADDON.getSetting('movie.rating.limit.enabled') == 'true':
            idx = MPAA_RATINGS.index(ADDON.getSetting('movie.rating.limit'))
            ratings = MPAA_RATINGS[idx:]

        elif gameInstance.getType() == game.GAMETYPE_TVSHOW and ADDON.getSetting('tvshow.rating.limit.enabled') == 'true':
            idx = CONTENT_RATINGS.index(ADDON.getSetting('tvshow.rating.limit'))
            ratings = CONTENT_RATINGS[idx:]

        onlyUsedWatched = ADDON.getSetting(SETT_ONLY_WATCHED_MOVIES) == 'true'

        self.database = db.Database.connect(ratings, onlyUsedWatched)
        self.player = player.TenSecondPlayer()

        self.questionPointsThread = None
        self.questionPoints = 0
        self.question = None
        self.previousQuestions = []
        self.lastClickTime = -1

        self.uiState = self.STATE_LOADING

    @buggalo.buggalo_try_except()
    def onInit(self):
        if self.gameInstance.getType() == game.GAMETYPE_TVSHOW:
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.defaultBackground)

        xbmc.sleep(500) # Opening animation
        self.onNewGame()

    def onNewGame(self):
        self.gameInstance.reset()

        self.questionPointsThread = None
        self.questionPoints = 0
        self.question = None
        self.previousQuestions = []
        self.uiState = self.STATE_LOADING

        self.onNewQuestion()

    def close(self):
        if self.player:
            if self.player.isPlaying():
                self.player.stop()
            self.player.close()
        self.database.close()
        super(QuizGui, self).close()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() == ACTION_PARENT_DIR or action.getId() == ACTION_PREVIOUS_MENU:
            self.onGameOver()

        if self.uiState == self.STATE_LOADING:
            return
        elif action.getId() in [ACTION_REMOTE1]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER)
            self.onQuestionAnswered(self.question.getAnswer(0))
        elif action.getId() in [ACTION_REMOTE2, ACTION_JUMP_SMS2]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 1)
            self.onQuestionAnswered(self.question.getAnswer(1))
        elif action.getId() in [ACTION_REMOTE3, ACTION_JUMP_SMS3]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 2)
            self.onQuestionAnswered(self.question.getAnswer(2))
        elif action.getId() in [ACTION_REMOTE4, ACTION_JUMP_SMS4]:
            self.setFocusId(self.C_MAIN_FIRST_ANSWER + 3)
            self.onQuestionAnswered(self.question.getAnswer(3))


    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        difference = time.time() - self.lastClickTime
        self.lastClickTime = time.time()
        if difference < 0.7:
            xbmc.log("Ignoring key-repeat onClick")
            return

        if not self.gameInstance.isInteractive():
            return # ignore
        elif controlId == self.C_MAIN_EXIT:
            self.onGameOver()
        elif self.uiState == self.STATE_LOADING:
            return # ignore the rest while we are loading
        elif self.question and (self.C_MAIN_FIRST_ANSWER <= controlId <= self.C_MAIN_LAST_ANSWER):
            answer = self.question.getAnswer(controlId - self.C_MAIN_FIRST_ANSWER)
            self.onQuestionAnswered(answer)
        elif controlId == self.C_MAIN_REPLAY:
            self.player.replay()

    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        self.onThumbChanged(controlId)

    def onGameOver(self):
        if self.uiState == self.STATE_GAME_OVER:
            return # ignore multiple invocations
        self.uiState = self.STATE_GAME_OVER

        if self.player.isPlaying():
            self.player.stop()

        if self.questionPointsThread is not None:
           self.questionPointsThread.cancel()

        if self.gameInstance.isInteractive():
            w = GameOverDialog(self, self.gameInstance)
            w.doModal()
            del w

    def onNewQuestion(self):
        if self.gameInstance.isGameOver():
            self.onGameOver()
            return

        self.onStatsChanged()
        self.uiState = self.STATE_LOADING
        self.getControl(self.C_MAIN_LOADING_VISIBILITY).setVisible(True)
        self.question = self._getNewQuestion()
        if not self.question:
            self.onGameOver()
            return
        self.getControl(self.C_MAIN_QUESTION_LABEL).setLabel(self.question.getText())

        answers = self.question.getAnswers()
        for idx in range(0, 4):
            button = self.getControl(self.C_MAIN_FIRST_ANSWER + idx)
            if idx >= len(answers):
                button.setLabel('')
                button.setVisible(False)
            else:
                button.setLabel(answers[idx].text, textColor='0xFFFFFFFF')
                button.setVisible(True)

            if not self.gameInstance.isInteractive() and answers[idx].correct:
                # highlight correct answer
                self.setFocusId(self.C_MAIN_FIRST_ANSWER + idx)

        self.onThumbChanged()

        if self.question.getFanartFile() is not None and os.path.exists(self.question.getFanartFile()):
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.question.getFanartFile())
        else:
            self.getControl(self.C_MAIN_MOVIE_BACKGROUND).setImage(self.defaultBackground)

        correctAnswer = self.question.getCorrectAnswer()
        displayType = self.question.getDisplayType()
        if isinstance(displayType, question.VideoDisplayType):
            self.getControl(self.C_MAIN_VIDEO_FILE_NOT_FOUND).setVisible(False)
            xbmc.sleep(1500) # give skin animation time to execute
            if not self.player.playWindowed(displayType.getVideoFile(), correctAnswer.idFile):
                self.getControl(self.C_MAIN_VIDEO_FILE_NOT_FOUND).setVisible(True)

        elif isinstance(displayType, question.PhotoDisplayType):
            self.getControl(self.C_MAIN_PHOTO).setImage(displayType.getPhotoFile())

        elif isinstance(displayType, question.ThreePhotoDisplayType):
            self.getControl(self.C_MAIN_PHOTO_1).setImage(displayType.getPhotoFile(0)[0])
            self.getControl(self.C_MAIN_PHOTO_LABEL_1).setLabel(displayType.getPhotoFile(0)[1])
            self.getControl(self.C_MAIN_PHOTO_2).setImage(displayType.getPhotoFile(1)[0])
            self.getControl(self.C_MAIN_PHOTO_LABEL_2).setLabel(displayType.getPhotoFile(1)[1])
            self.getControl(self.C_MAIN_PHOTO_3).setImage(displayType.getPhotoFile(2)[0])
            self.getControl(self.C_MAIN_PHOTO_LABEL_3).setLabel(displayType.getPhotoFile(2)[1])

        elif isinstance(displayType, question.QuoteDisplayType):
            quoteText = displayType.getQuoteText()
            quoteText = self._obfuscateQuote(quoteText)
            self.getControl(self.C_MAIN_QUOTE_LABEL).setText(quoteText)

        elif isinstance(displayType, question.AudioDisplayType):
            self.player.playAudio(displayType.getAudioFile())

        self.onVisibilityChanged(displayType)

        if not self.gameInstance.isInteractive():
            # answers correctly in ten seconds
            threading.Timer(10.0, self._answer_correctly).start()

        self.uiState = self.STATE_PLAYING
        self.getControl(self.C_MAIN_LOADING_VISIBILITY).setVisible(False)

        self.questionPoints = None
        self.onQuestionPointTimer()

    def _getNewQuestion(self):
        retries = 0
        q = None
        while retries < 100 and self.uiState == self.STATE_LOADING:
            xbmc.sleep(10) # give XBMC time to process other events
            retries += 1

            self.getControl(self.C_MAIN_LOADING).setPercent(retries)

            q = question.getRandomQuestion(self.gameInstance, self.database)
            if q is None:
                continue
            
            if not q.getUniqueIdentifier() in self.previousQuestions:
                self.previousQuestions.append(q.getUniqueIdentifier())
                break

        return q

    @buggalo.buggalo_try_except()
    def onQuestionPointTimer(self):
        """
        onQuestionPointTimer handles the decreasing amount of points awareded to the user when a question is answered correctly.

        The points start a 100 and is decreasing exponentially slower to make it more difficult to get a higher score.
        When the points reach 10 the decreasing ends, making 10 the lowes score you can get.

        Before the timer starts the user gets a three second head start - this is to actually make it possible to get a perfect 100 score.
        """
        if self.questionPointsThread is not None:
           self.questionPointsThread.cancel()

        if self.questionPoints is None:
            self.questionPoints = 100
        else:
            self.questionPoints -= 1
            
        self.getControl(4103).setLabel(str(self.questionPoints / 10.0))
        if self.questionPoints == 100:
            # three second head start
            self.questionPointsThread = threading.Timer(3, self.onQuestionPointTimer)
            self.questionPointsThread.start()
        elif self.questionPoints > 10:
            seconds = (100 - self.questionPoints) / 100.0
            self.questionPointsThread = threading.Timer(seconds, self.onQuestionPointTimer)
            self.questionPointsThread.start()

    def _answer_correctly(self):
        answer = self.question.getCorrectAnswer()
        self.onQuestionAnswered(answer)

    def onQuestionAnswered(self, answer):
        """
        @param answer: the chosen answer by the user
        @type answer: Answer
        """
        xbmc.log("onQuestionAnswered(..)")
        if self.questionPointsThread is not None:
           self.questionPointsThread.cancel()

        if answer is not None and answer.correct:
            xbmc.playSFX(AUDIO_CORRECT)
            self.gameInstance.correctAnswer(self.questionPoints / 10.0)
            self.getControl(self.C_MAIN_CORRECT_VISIBILITY).setVisible(False)
        else:
            xbmc.playSFX(AUDIO_WRONG)
            self.gameInstance.wrongAnswer()
            self.getControl(self.C_MAIN_INCORRECT_VISIBILITY).setVisible(False)

        if self.player.isPlaying():
            self.player.stop()

        threading.Timer(0.5, self.onQuestionAnswerFeedbackTimer).start()
        if ADDON.getSetting('show.correct.answer') == 'true' and not answer.correct:
            for idx, answer in enumerate(self.question.getAnswers()):
                if answer.correct:
                    self.getControl(self.C_MAIN_FIRST_ANSWER + idx).setLabel('[B]%s[/B]' % answer.text)
                    self.setFocusId(self.C_MAIN_FIRST_ANSWER + idx)
                    self.onThumbChanged(self.C_MAIN_FIRST_ANSWER + idx)
                else:
                    self.getControl(self.C_MAIN_FIRST_ANSWER + idx).setLabel(textColor='0x88888888')

            if isinstance(self.question.getDisplayType(), question.QuoteDisplayType):
                # Display non-obfuscated quote text
                self.getControl(self.C_MAIN_QUOTE_LABEL).setText(self.question.getDisplayType().getQuoteText())

            xbmc.sleep(3000)

        if self.uiState != self.STATE_GAME_OVER:
            self.onNewQuestion()

    def onStatsChanged(self):
        self.getControl(self.C_MAIN_CORRECT_SCORE).setLabel(str(self.gameInstance.getPoints()))

        label = self.getControl(self.C_MAIN_QUESTION_COUNT)
        label.setLabel(self.gameInstance.getStatsString())
        
    def onThumbChanged(self, controlId = None):
        if self.question is None:
            return # not initialized yet

        if controlId is None:
            controlId = self.getFocusId()

        if self.C_MAIN_FIRST_ANSWER <= controlId <= self.C_MAIN_LAST_ANSWER:
            answer = self.question.getAnswer(controlId - self.C_MAIN_FIRST_ANSWER)
            coverImage = self.getControl(self.C_MAIN_COVER_IMAGE)
            if answer is not None and answer.coverFile is not None and os.path.exists(answer.coverFile):
                self.getControl(self.C_MAIN_COVER_IMAGE_VISIBILITY).setVisible(False)
                coverImage.setImage(answer.coverFile)
            elif answer is not None and answer.coverFile is not None :
                self.getControl(self.C_MAIN_COVER_IMAGE_VISIBILITY).setVisible(False)
                coverImage.setImage(NO_PHOTO_IMAGE)
            else:
                self.getControl(self.C_MAIN_COVER_IMAGE_VISIBILITY).setVisible(True)

    @buggalo.buggalo_try_except()
    def onQuestionAnswerFeedbackTimer(self):
        """
        onQuestionAnswerFeedbackTimer is invoked by a timer when the red or green background behind the answers box
        must be faded out and hidden.

        Note: Visibility is inverted in skin
        """
        self.getControl(self.C_MAIN_CORRECT_VISIBILITY).setVisible(True)
        self.getControl(self.C_MAIN_INCORRECT_VISIBILITY).setVisible(True)

    def onVisibilityChanged(self, displayType = None):
        """
        @type displayType: quizlib.question.DisplayType
        @param displayType: the type of display required by the current question
        """
        self.getControl(self.C_MAIN_VIDEO_VISIBILITY).setVisible(not isinstance(displayType, question.VideoDisplayType))
        self.getControl(self.C_MAIN_PHOTO_VISIBILITY).setVisible(not isinstance(displayType, question.PhotoDisplayType))
        self.getControl(self.C_MAIN_QUOTE_VISIBILITY).setVisible(not isinstance(displayType, question.QuoteDisplayType))
        self.getControl(self.C_MAIN_THREE_PHOTOS_VISIBILITY).setVisible(not isinstance(displayType, question.ThreePhotoDisplayType))
        self.getControl(self.C_MAIN_THEME_VISIBILITY).setVisible(not isinstance(displayType, question.AudioDisplayType))


    def _obfuscateQuote(self, quote):
        names = list()

        for m in re.finditer('(\[.*?\])', quote, re.DOTALL):
            quote = quote.replace(m.group(1), '')

        for m in re.finditer('(.*?:)', quote):
            name = m.group(1)
            if not name in names:
                names.append(name)

        for idx, name in enumerate(names):
            repl = '#%d:' % (idx + 1)
            quote = quote.replace(name, repl)

        return quote


class GameOverDialog(xbmcgui.WindowXMLDialog):
    C_GAMEOVER_VISIBILITY_MARKER = 100

    C_GAMEOVER_RETRY = 4000
    C_GAMEOVER_GLOBAL_HIGHSCORE = 4001
    C_GAMEOVER_HIGHSCORE = 4002
    C_GAMEOVER_MAINMENU = 4003

    C_GAMEOVER_GLOBAL_HIGHSCORE_LIST = 8001
    C_GAMEOVER_GLOBAL_HIGHSCORE_TYPE = 8002

    C_GAMEOVER_LOCAL_HIGHSCORE_LIST = 9001
    C_GAMEOVER_LOCAL_HIGHSCORE_TYPE = 9002

    VISIBLE_GLOBAL_HIGHSCORE = 'globalHighscore'
    VISIBLE_LOCAL_HIGHSCORE = 'localHighscore'

    def __new__(cls, parentWindow, gameType):
        return super(GameOverDialog, cls).__new__(cls, 'script-moviequiz-gameover.xml', ADDON.getAddonInfo('path'))

    def __init__(self, parentWindow, game):
        super(GameOverDialog, self).__init__()

        self.parentWindow = parentWindow
        self.game = game

    @buggalo.buggalo_try_except()
    def onInit(self):
        self.getControl(4100).setLabel(strings(G_YOU_SCORED) % (self.game.getCorrectAnswers(), self.game.getTotalAnswers()))
        self.getControl(4101).setLabel(str(self.game.getPoints()))

        if self.game.isInteractive():
            self._setupHighscores()

    @buggalo.buggalo_try_except()
    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU]:
            self.close()
            self.parentWindow.close()

    @buggalo.buggalo_try_except()
    def onClick(self, controlId):
        if controlId == self.C_GAMEOVER_RETRY:
            self.parentWindow.onNewGame()
            self.close()

        elif controlId == self.C_GAMEOVER_MAINMENU:
            self.close()
            self.parentWindow.close()

    @buggalo.buggalo_try_except()
    def onFocus(self, controlId):
        if controlId in [self.C_GAMEOVER_RETRY, self.C_GAMEOVER_MAINMENU]:
            self.getControl(self.C_GAMEOVER_VISIBILITY_MARKER).setLabel('')
        elif controlId == self.C_GAMEOVER_GLOBAL_HIGHSCORE:
            self.getControl(self.C_GAMEOVER_VISIBILITY_MARKER).setLabel(self.VISIBLE_GLOBAL_HIGHSCORE)
        elif controlId == self.C_GAMEOVER_HIGHSCORE:
            self.getControl(self.C_GAMEOVER_VISIBILITY_MARKER).setLabel(self.VISIBLE_LOCAL_HIGHSCORE)

    def _setupHighscores(self):
        # Local highscore
        localHighscore = highscore.LocalHighscoreDatabase(xbmc.translatePath(ADDON.getAddonInfo('profile')))
        newHighscoreId = localHighscore.addHighscore(self.game)
        name = localHighscore.getNickname(self.game.getUserId())

        entries = localHighscore.getHighscoresNear(self.game, newHighscoreId)
        localHighscore.close()

        subTypeText = None
        if isinstance(self.game, game.UnlimitedGame):
            subTypeText = strings(M_UNLIMITED)
        elif isinstance(self.game, game.QuestionLimitedGame):
            subTypeText = strings(M_X_QUESTIONS_LIMIT, self.game.getGameSubType())

        elif isinstance(self.game, game.TimeLimitedGame):
            if int(self.game.getGameSubType()) == 1:
                subTypeText = strings(M_ONE_MINUT_LIMIT)
            else:
                subTypeText = strings(M_X_MINUTS_LIMIT, self.game.getGameSubType())

        self.getControl(self.C_GAMEOVER_LOCAL_HIGHSCORE_TYPE).setLabel(subTypeText)
        items = list()
        selectedIndex = -1
        for entry in entries:
            item = xbmcgui.ListItem("%d. %s" % (entry['position'], entry['nickname']))
            item.setProperty('score', str(entry['score']))
            if int(entry['id']) == int(newHighscoreId):
                item.setProperty('highlight', 'true')
                selectedIndex = len(items)
            items.append(item)
        listControl = self.getControl(self.C_GAMEOVER_LOCAL_HIGHSCORE_LIST)
        listControl.addItems(items)
        if selectedIndex != -1:
            selectedIndex += 5
            if selectedIndex > len(items):
                selectedIndex = len(items) - 1
            listControl.selectItem(selectedIndex)

        # Global highscore
        globalHighscore = highscore.GlobalHighscoreDatabase(ADDON.getAddonInfo('version'))
        if ADDON.getSetting('submit.highscores') == 'true':
            newHighscoreId = globalHighscore.addHighscore(name, self.game)
        else:
            newHighscoreId = -1

        entries = globalHighscore.getHighscoresNear(self.game, newHighscoreId)
        self.getControl(self.C_GAMEOVER_GLOBAL_HIGHSCORE_TYPE).setLabel(subTypeText)
        items = list()
        selectedIndex = -1
        for entry in entries:
            item = xbmcgui.ListItem("%s. %s" % (entry['position'], entry['nickname']))
            item.setProperty('score', str(entry['score']))
            if int(entry['id']) == int(newHighscoreId):
                item.setProperty('highlight', 'true')
                selectedIndex = len(items)
            items.append(item)
        listControl = self.getControl(self.C_GAMEOVER_GLOBAL_HIGHSCORE_LIST)
        listControl.addItems(items)
        if selectedIndex != -1:
            selectedIndex += 5
            if selectedIndex > len(items):
                selectedIndex = len(items) - 1
            listControl.selectItem(selectedIndex)
