from src.persistence.mongo_logger import MongoConversationLogger


def main():
    # 1. 创建logger
    logger = MongoConversationLogger()

    # 2. 写入一条测试数据
    logger.log_message(
        session_id="test_session_001",
        sender="User",
        receiver="Coordinator",
        content="你好，这是测试消息",
        raw_message={"type": "test"},
    )

    # 3. 关闭连接
    logger.close()


if __name__ == "__main__":
    main()
