"""运行所有实验"""
import sys
from pathlib import Path

# 确保可以导入src模块
sys.path.insert(0, str(Path(__file__).parent))

from experiment_rag_accuracy import run_rag_accuracy_experiment
from experiment_compression_rate import run_compression_experiment


def main():
    print("\n" + "=" * 70)
    print(" " * 20 + "开始运行实验套件")
    print("=" * 70 + "\n")

    try:
        # 实验1: RAG准确度对比
        print("\n🔬 运行实验1: RAG准确度对比")
        rag_results = run_rag_accuracy_experiment()

        print("\n" + "-" * 70 + "\n")

        # 实验2: 消息压缩率
        print("\n🔬 运行实验2: 消息压缩率测试")
        compression_results = run_compression_experiment()

        # 综合总结
        print("\n" + "=" * 70)
        print(" " * 25 + "实验总结")
        print("=" * 70)

        print("\n📊 实验1 - RAG准确度提升:")
        print(f"  • 无RAG平均准确度: {rag_results['without_rag']['average']:.2%}")
        print(f"  • 有RAG平均准确度: {rag_results['with_rag']['average']:.2%}")
        print(f"  • 准确度提升: {rag_results['improvement_percentage']:.1f}%")

        print("\n📊 实验2 - 消息压缩率:")
        for level, data in compression_results.items():
            print(f"  • {level:12s} 级别: {data['overall_ratio']:.1f}% 压缩率")

        print("\n✅ 所有实验完成！结果已保存到 experiment_results/ 目录")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ 实验运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
