"""
测试消息压缩的实际效果，计算真实的压缩率。
"""

from src.rag.message_compressor import MessageCompressor, CompressionLevel

# 模拟一个真实的多智能体协作历史对话
sample_conversation = [
    {
        "role": "user",
        "content": "帮我开发一个学生管理系统，后端用Java Spring Boot，数据库用MySQL，前端用Vue。要求支持学生的增删改查，并且要有权限管理。",
    },
    {
        "role": "coordinator",
        "content": """好的，我理解了。我来分解这个需求：

## 任务分解
1. **数据库设计**：创建学生表、权限表等
2. **后端API开发**：使用Spring Boot实现RESTful接口
3. **前端界面**：使用Vue.js开发管理界面
4. **权限管理**：实现基于角色的访问控制

让我先请产品经理确认需求细节。""",
    },
    {
        "role": "product_manager",
        "content": """确认！基于您的描述，我整理了需求文档：

### 功能需求
- 学生信息管理（增删改查）
- 权限管理（管理员、教师、学生三种角色）
- 搜索和筛选功能
- 数据导出

### 技术栈
- 后端：Java 17 + Spring Boot 3.0 + MySQL 8.0
- 前端：Vue 3 + Vite + Element Plus
- 部署：Docker + Docker Compose

### 数据模型
```
Students: id, name, email, phone, created_at
Users: id, username, password, role_id
Roles: id, role_name, permissions
```

我们可以开始开发了。""",
    },
    {
        "role": "engineer",
        "content": """收到！我开始开发后端。

### 后端项目结构
```
src/
├── main/
│   ├── java/
│   │   └── com/studentmanagement/
│   │       ├── controller/
│   │       ├── service/
│   │       ├── repository/
│   │       ├── entity/
│   │       ├── dto/
│   │       └── exception/
│   └── resources/
│       ├── application.yml
│       └── schema.sql
└── test/
```

### 核心实体类

```java
@Entity
@Table(name = "students")
public class Student {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private String name;
    
    @Column(nullable = false, unique = true)
    private String email;
    
    private String phone;
    
    @CreationTimestamp
    private LocalDateTime createdAt;
}
```

### API端点设计
- POST /api/students - 创建学生
- GET /api/students - 获取所有学生
- GET /api/students/{id} - 获取单个学生
- PUT /api/students/{id} - 更新学生
- DELETE /api/students/{id} - 删除学生

代码已上传，请测试。""",
    },
    {
        "role": "qa_engineer",
        "content": """开始测试。我会验证以下内容：

1. **单元测试**
   - StudentController 的各个端点
   - StudentService 的业务逻辑
   - 权限检查

2. **集成测试**
   - 数据库连接
   - 事务处理
   - 异常处理

3. **API测试**
   - 创建学生：POST /api/students ✓
   - 查询学生：GET /api/students ✓
   - 更新学生：PUT /api/students/1 ✓
   - 删除学生：DELETE /api/students/1 ✓

4. **权限测试**
   - 管理员能删除学生 ✓
   - 教师不能删除学生 ✓
   - 学生不能修改他人信息 ✓

**结果：所有测试通过！** 

建议：
- 添加更多的验证规则
- 完善错误提示
- 性能测试待补充""",
    },
    {
        "role": "coordinator",
        "content": """很好！QA报告已收到。我汇总当前状态：

✅ **已完成**
- 后端API开发（Spring Boot）
- 数据库设计（MySQL）
- 权限管理实现
- 单元测试和集成测试通过

📝 **待处理**
- 前端界面开发（Vue）
- 前后端联调
- 性能优化
- 文档完善

工程师，请继续开发前端。""",
    },
    {
        "role": "engineer",
        "content": """收到！前端开发中...

### 前端项目结构
```
src/
├── components/
│   ├── StudentForm.vue
│   ├── StudentTable.vue
│   └── RoleSelector.vue
├── views/
│   ├── StudentManagement.vue
│   └── Dashboard.vue
├── services/
│   └── api.js
└── router/
    └── index.js
```

### 关键组件

**StudentTable.vue**
```vue
<template>
  <el-table :data="students" stripe style="width: 100%">
    <el-table-column prop="id" label="学号" width="80" />
    <el-table-column prop="name" label="姓名" width="120" />
    <el-table-column prop="email" label="邮箱" width="200" />
    <el-table-column label="操作" width="200">
      <template #default="scope">
        <el-button @click="handleEdit(scope.row)">编辑</el-button>
        <el-button type="danger" @click="handleDelete(scope.row.id)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
```

前端代码已完成。""",
    },
    {
        "role": "qa_engineer",
        "content": """前端测试完成：

✅ 学生列表显示正常
✅ 创建学生表单可用
✅ 编辑功能正常
✅ 删除确认机制生效
✅ 权限控制生效（非管理员看不到删除按钮）
✅ 前后端联调成功

所有功能测试通过！可以上线。""",
    },
    {
        "role": "coordinator",
        "content": """最终验收：

✅ **功能完整性**：所有功能已实现
✅ **测试覆盖**：单元测试、集成测试、前端测试都通过
✅ **文档齐全**：API文档、部署指南已完成
✅ **权限管理**：三层角色权限正常生效

**验收通过**

## 交付物清单
1. 后端代码：src/main/java/com/studentmanagement/
2. 前端代码：src/components/、src/views/
3. 数据库脚本：schema.sql
4. 测试用例：test/目录
5. API文档：docs/api.md
6. 部署指南：DEPLOYMENT.md

## 运行方式
1. 数据库：docker run -d -e MYSQL_ROOT_PASSWORD=password mysql:8.0
2. 后端：mvn spring-boot:run
3. 前端：npm run dev

项目已交付，任务完成。

TERMINATE""",
    },
]


def test_compression():
    """测试不同压缩级别的效果"""

    # 合并所有对话内容
    full_content = "\n\n".join([msg["content"] for msg in sample_conversation])

    original_size = len(full_content.encode("utf-8"))
    print(f"📊 原始对话大小: {original_size} 字节")
    print(f"📝 原始对话字符数: {len(full_content)} 字符\n")
    print("=" * 80)

    # 测试不同压缩级别
    levels = [
        ("NONE", CompressionLevel.NONE),
        ("LIGHT", CompressionLevel.LIGHT),
        ("MODERATE", CompressionLevel.MODERATE),
        ("AGGRESSIVE", CompressionLevel.AGGRESSIVE),
    ]

    results = []

    for level_name, level in levels:
        compressor = MessageCompressor(level=level, preserve_structure=True)
        compressed = compressor.compress(full_content)

        compressed_size = len(compressed.encode("utf-8"))
        compression_ratio = (1.0 - compressed_size / original_size) * 100

        results.append(
            {
                "level": level_name,
                "original": original_size,
                "compressed": compressed_size,
                "ratio": compression_ratio,
                "saved": original_size - compressed_size,
            }
        )

        print(f"🔧 {level_name} 压缩级别")
        print(f"   压缩后大小: {compressed_size} 字节")
        print(f"   压缩率: {compression_ratio:.1f}%")
        print(f"   节省空间: {original_size - compressed_size} 字节")
        print()

    print("=" * 80)
    print("\n📈 压缩效果对比总结\n")

    for result in results:
        bar_length = int(result["ratio"] / 2)
        bar = "█" * bar_length + "░" * (50 - bar_length)
        print(f"{result['level']:12} │{bar}│ {result['ratio']:5.1f}%")

    print()
    print("=" * 80)
    print("\n💡 关键发现：")
    print(f"- MODERATE 级别（推荐）达到 {results[2]['ratio']:.1f}% 的压缩率")
    print(f"- 将 {original_size} 字节压缩到 {results[2]['compressed']} 字节")
    print(f"- 相当于节省了 {results[2]['saved']} 字节的存储空间")
    print(f"- 上下文窗口可容纳更多的消息轮次")


if __name__ == "__main__":
    test_compression()
