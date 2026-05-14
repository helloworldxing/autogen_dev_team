"""检查 MongoDB 连接和配置。"""

import os
from dotenv import load_dotenv
from src.persistence.mongo_logger import MongoConversationLogger

load_dotenv()

print("=" * 60)
print("🔍 MongoDB 连接诊断")
print("=" * 60)

# 检查环境变量
print("\n📋 环境变量配置：")
mongo_enabled = os.getenv("MONGO_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
mongo_db = os.getenv("MONGO_DB", "autogen_dev_team")
mongo_collection = os.getenv("MONGO_COLLECTION", "conversation_messages")

print(f"  • MONGO_ENABLED: {mongo_enabled}")
print(f"  • MONGO_URI: {mongo_uri}")
print(f"  • MONGO_DB: {mongo_db}")
print(f"  • MONGO_COLLECTION: {mongo_collection}")

# 测试连接
print("\n🔗 测试连接...")
logger = MongoConversationLogger()

if logger.enabled and logger.collection is not None:
    print("✅ MongoDB 连接成功！")

    # 测试写入
    print("\n📝 测试数据写入...")
    try:
        logger.log_message(
            session_id="test-session-001",
            receiver="test-receiver",
            sender="test-sender",
            content="这是一条测试消息，用来验证 MongoDB 是否正常工作。",
        )
        print("✅ 测试数据写入成功！")

        # 查询验证
        if logger.collection is not None:
            doc = logger.collection.find_one({"session_id": "test-session-001"})
            if doc:
                print(f"✅ 数据库查询成功，已验证数据存储：")
                print(f"   • Session ID: {doc['session_id']}")
                print(f"   • Sender: {doc['sender']}")
                print(f"   • Receiver: {doc['receiver']}")
                print(f"   • Content: {doc['content'][:50]}...")
            else:
                print("⚠️  数据未找到（可能是查询延迟）")
    except Exception as e:
        print(f"❌ 数据写入失败: {e}")
else:
    print("❌ MongoDB 连接失败或已禁用！")
    print("   请检查：")
    print("   1. MongoDB 服务是否运行：mongodb://localhost:27017")
    print("   2. 防火墙是否阻止了连接")
    print("   3. .env 中是否正确配置了 MONGO_URI")
    print("   4. MONGO_ENABLED 是否设为 true")

print("\n" + "=" * 60)
