"""查看 MongoDB 中存储的所有对话数据。"""

from src.persistence.mongo_logger import MongoConversationLogger

logger = MongoConversationLogger()

if logger.collection is not None:
    count = logger.collection.count_documents({})
    print(f"\n📊 MongoDB 中共有 {count} 条消息\n")

    if count == 0:
        print("⚠️  数据库为空，还没有任务执行记录。")
        print("   请运行任务后再检查。\n")
    else:
        # 显示最近 10 条
        print("📋 最近的消息：")
        print("-" * 80)
        for i, doc in enumerate(logger.collection.find().sort("_id", -1).limit(10), 1):
            sender = doc.get("sender", "unknown")
            receiver = doc.get("receiver", "unknown")
            content = doc.get("content", "")[:60]
            timestamp = doc.get("timestamp", "N/A")
            print(f"{i}. [{sender}→{receiver}] {timestamp}")
            print(f"   内容: {content}...")
            print()

        # 按 session_id 统计
        print("-" * 80)
        print("\n📊 按 Session 统计：")
        sessions = logger.collection.aggregate(
            [
                {"$group": {"_id": "$session_id", "count": {"$sum": 1}}},
                {"$sort": {"_id": -1}},
                {"$limit": 5},
            ]
        )
        for session in sessions:
            print(f"   Session {session['_id']}: {session['count']} 条消息")
else:
    print("❌ MongoDB 连接失败")
