from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf


class Session(object):
    def __init__(self, session_id, system_prompt=None, model=None):
        self.session_id = session_id
        self.messages = []
        self.model = model
        if system_prompt is None:
            self.system_prompt = conf().get("character_desc", "")
        else:
            self.system_prompt = system_prompt

    # 重置会话
    def reset(self):
        system_item = {"role": "system", "content": self.system_prompt}
        self.messages = [system_item]

    def set_system_prompt(self, system_prompt):
        self.system_prompt = system_prompt
        self.reset()

    def set_model(self, model):
        self.model = model
        self.reset()

    def add_query(self, query):
        user_item = {"role": "user", "content": query}
        self.messages.append(user_item)

    def add_reply(self, reply):
        assistant_item = {"role": "assistant", "content": reply}
        self.messages.append(assistant_item)

    def discard_exceeding(self, max_tokens=None, cur_tokens=None):
        raise NotImplementedError

    def calc_tokens(self):
        raise NotImplementedError


class SessionManager(object):
    def __init__(self, sessioncls, **session_args):
        if conf().get("expires_in_seconds"):
            sessions = ExpiredDict(conf().get("expires_in_seconds"))
        else:
            sessions = dict()
        self.sessions = sessions
        self.sessioncls = sessioncls
        self.default_model = session_args["default_model"]

    def build_session(self, session_id, system_prompt=None, user_model=None):
        """
        如果session_id不在sessions中，创建一个新的session并添加到sessions中
        如果system_prompt不会空，会更新session的system_prompt并重置session
        """
        model = user_model or self.default_model
        if session_id is None:
            return self.sessioncls(session_id, system_prompt, model)
        if session_id not in self.sessions:
            self.sessions[session_id] = self.sessioncls(session_id, system_prompt, model)

        session = self.sessions[session_id]
        if system_prompt is not None:  # 如果有新的system_prompt，更新并重置session
            session.set_system_prompt(system_prompt)
        if user_model is not None and session.model != user_model: # 如果有新的model，更新并重置model
            session.set_model(user_model)
        print("session.model=", session.model)
        return session

    def session_query(self, query, session_id, user_model=None):
        session = self.build_session(session_id, None, user_model)
        session.add_query(query)
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)
            total_tokens = session.discard_exceeding(max_tokens, None)
            logger.debug("prompt tokens used={}".format(total_tokens))
        except Exception as e:
            logger.debug("Exception when counting tokens precisely for prompt: {}".format(str(e)))
        return session

    def session_reply(self, reply, session_id, total_tokens=None):
        session = self.build_session(session_id)
        session.add_reply(reply)
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)
            tokens_cnt = session.discard_exceeding(max_tokens, total_tokens)
            logger.debug("raw total_tokens={}, savesession tokens={}".format(total_tokens, tokens_cnt))
        except Exception as e:
            logger.debug("Exception when counting tokens precisely for session: {}".format(str(e)))
        return session

    def clear_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def clear_all_session(self):
        self.sessions.clear()
