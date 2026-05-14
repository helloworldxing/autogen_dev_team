"""Attach RAG retrieval to AutoGen agents."""

from __future__ import annotations


class RAGAgentWrapper:
    """Wrap an AutoGen agent to inject retrieved context before reply generation."""

    def __init__(self, agent, knowledge_base):
        self.agent = agent
        self.kb = knowledge_base

        original_generate = agent.generate_reply

        # autogen binds generate_reply as an instance method; here we rebind with MethodType
        # so that calls like generate_reply(sender=manager) work (self is the agent instance).
        def rag_generate_reply(self_agent, messages=None, sender=None, **kwargs):
            msgs = messages
            if msgs is None:
                if sender is not None and hasattr(self_agent, "chat_messages"):
                    msgs = self_agent.chat_messages.get(sender, [])
                else:
                    msgs = []

            if msgs and isinstance(msgs[-1], dict):
                user_input = msgs[-1].get("content", "")
            else:
                user_input = ""

            context = self.kb.retrieve_context(user_input)

            if context and msgs and isinstance(msgs[-1], dict):
                msgs[-1]["content"] = user_input + context

            return original_generate(messages=msgs, sender=sender, **kwargs)

        import types

        agent.generate_reply = types.MethodType(rag_generate_reply, agent)

    def get_agent(self):
        return self.agent
