clarify_with_user_prompt = """These are the messages that have been exchanged so far from the user asking for the novel:
<Messages>
{messages}
</Messages>

Assess whether you need to ask a clarifying question, or if the user has already provided enough information for you to start write a novel.
IMPORTANT: If you can see in the messages history that you have already asked a clarifying question, you almost always do not need to ask another one. Only ask another question if ABSOLUTELY NECESSARY.

If there are acronyms, abbreviations, or unknown terms, ask the user to clarify.
If you need to ask a question, follow these guidelines:
- Be concise while gathering all necessary information
- Make sure to gather all the information needed to carry out the write a novel in a concise, well-structured manner.
- Use bullet points or numbered lists if appropriate for clarity. Make sure that this uses markdown formatting and will be rendered correctly if the string output is passed to a markdown renderer.
- Don't ask for unnecessary information, or information that the user has already provided. If you can see that the user has already provided the information, do not ask for it again.

Respond in valid JSON format with these exact keys:
"need_clarification": boolean,
"question": "<question to ask the user to clarify the report scope>",
"verification": "<verification message that we will start research>"

If you need to ask a clarifying question, return:
"need_clarification": true,
"question": "<your clarifying question>",
"verification": ""

If you do not need to ask a clarifying question, return:
"need_clarification": false,
"question": "",
"verification": "<acknowledgement message that you will now start research based on the provided information>"

If the messages is in a specific language, prioritize sources published in that language.

For the verification message when no clarification is needed:
- Acknowledge that you have sufficient information to proceed
- Briefly summarize the key settings of what you understand from their request
- Keep the message concise and professional
- The key settings include topic(the topic of novel), genre(the genre of novel), count_of_chapters(the number of chapters in a novel), word_numbers(the word count of each chapter in the novel)
"""

extract_setting_prompt = """You will be given a set of messages that have been exchanged so far between yourself and the user. 
Your job is to extract **key settings** from these messages

The messages that have been exchanged so far between yourself and the user are:
<Messages>
{messages}
</Messages>

You will return **key settings** that will be used to guide the novel.

Guidelines:
The key settings include: 
- topic: the topic of novel
- genre: the genre of novel
- count_of_chapters: the number of chapters in a novel
- word_numbers: the word count of each chapter in the novel
"""

# =============== 1. 核心种子设定（雪花第1层）===================
core_seed_prompt = """\
作为专业作家，请用"雪花写作法"第一步构建故事核心：
主题：{topic}
类型：{genre}
篇幅：约{number_of_chapters}章（每章{word_number}字）

请用单句公式概括故事本质，例如：
"当[主角]遭遇[核心事件]，必须[关键行动]，否则[灾难后果]；与此同时，[隐藏的更大危机]正在发酵。"

要求：
1. 必须包含显性冲突与潜在危机
2. 体现人物核心驱动力
3. 暗示世界观关键矛盾
4. 使用25-100字精准表达

仅返回故事核心文本，不要解释任何内容。
"""
# =============== 2. 角色动力学设定（角色弧光模型）===================
character_dynamics_prompt = """\
基于以下元素：
- 核心种子：{core_seed_result}

请设计3-6个具有动态变化潜力的核心角色，每个角色需包含：
特征：
- 背景、外貌、性别、年龄、职业等
- 暗藏的秘密或潜在弱点(可与世界观或其他角色有关)

核心驱动力三角：
- 表面追求（物质目标）
- 深层渴望（情感需求）
- 灵魂需求（哲学层面）

角色弧线设计：
初始状态 → 触发事件 → 认知失调 → 蜕变节点 → 最终状态

关系冲突网：
- 与其他角色的关系或对立点
- 与至少两个其他角色的价值观冲突
- 一个合作纽带
- 一个隐藏的背叛可能性

要求：
仅给出最终文本，不要解释任何内容。
"""


# =============== 3. 世界构建矩阵（三维度交织法）===================
world_building_prompt = """\
基于以下元素：
- 核心冲突："{core_seed_result}"

为服务上述内容，请构建三维交织的世界观：

1. 物理维度：
- 空间结构（地理×社会阶层分布图）
- 时间轴（关键历史事件年表）
- 法则体系（物理/魔法/社会规则的漏洞点）

2. 社会维度：
- 权力结构断层线（可引发冲突的阶层/种族/组织矛盾）
- 文化禁忌（可被打破的禁忌及其后果）
- 经济命脉（资源争夺焦点）

3. 隐喻维度：
- 贯穿全书的视觉符号系统（如反复出现的意象）
- 氣候/环境变化映射的心理状态
- 建筑风格暗示的文明困境

要求：
每个维度至少包含3个可与角色决策产生互动的动态元素。
仅给出最终文本，不要解释任何内容。
"""

# =============== 4. 情节架构（三幕式悬念）===================
plot_arch_prompt = """\
基于以下元素：
- 核心种子：{core_seed_result}
- 角色体系：{character_dynamics_result}
- 世界观：{world_building_result}

要求按以下结构设计：
第一幕（触发） 
- 日常状态中的异常征兆（3处铺垫）
- 引出故事：展示主线、暗线、副线的开端
- 关键事件：打破平衡的催化剂（需改变至少3个角色的关系）
- 错误抉择：主角的认知局限导致的错误反应

第二幕（对抗）
- 剧情升级：主线+副线的交叉点
- 双重压力：外部障碍升级+内部挫折
- 虚假胜利：看似解决实则深化危机的转折点
- 灵魂黑夜：世界观认知颠覆时刻

第三幕（解决）
- 代价显现：解决危机必须牺牲的核心价值
- 嵌套转折：至少包含三层认知颠覆（表面解→新危机→终极抉择）
- 余波：留下2个开放式悬念因子

每个阶段需包含3个关键转折点及其对应的伏笔回收方案。
仅给出最终文本，不要解释任何内容。
"""

# =============== 5. 章节目录生成（悬念节奏曲线）===================
chapter_blueprint_prompt = """\
基于以下元素：
- 内容指导：{user_guidance}
- 小说架构：
{novel_architecture}

设计{number_of_chapters}章的节奏分布：
1. 章节集群划分：
- 每3-5章构成一个悬念单元，包含完整的小高潮
- 单元之间设置"认知过山车"（连续2章紧张→1章缓冲）
- 关键转折章需预留多视角铺垫

2. 每章需明确：
- 章节定位（角色/事件/主题等）
- 核心悬念类型（信息差/道德困境/时间压力等）
- 情感基调迁移（如从怀疑→恐惧→决绝）
- 伏笔操作（埋设/强化/回收）
- 认知颠覆强度（1-5级）

输出格式示例：
第n章 - [标题]
本章定位：[角色/事件/主题/...]
核心作用：[推进/转折/揭示/...]
悬念密度：[紧凑/渐进/爆发/...]
伏笔操作：埋设(A线索)→强化(B矛盾)...
认知颠覆：★☆☆☆☆
本章简述：[一句话概括]

第n+1章 - [标题]
本章定位：[角色/事件/主题/...]
核心作用：[推进/转折/揭示/...]
悬念密度：[紧凑/渐进/爆发/...]
伏笔操作：埋设(A线索)→强化(B矛盾)...
认知颠覆：★☆☆☆☆
本章简述：[一句话概括]

要求：
- 使用精炼语言描述，每章字数控制在100字以内。
- 合理安排节奏，确保整体悬念曲线的连贯性。
- 在生成{number_of_chapters}章前不要出现结局章节。

仅给出最终文本，不要解释任何内容。
"""

chunked_chapter_blueprint_prompt = """\
基于以下元素：
- 内容指导：{user_guidance}
- 小说架构：
{novel_architecture}

需要生成总共{number_of_chapters}章的节奏分布，

当前已有章节目录（若为空则说明是初始生成）：\n
{chapter_list}

现在请设计第{start}章到第{end}的节奏分布：
1. 章节集群划分：
- 每3-5章构成一个悬念单元，包含完整的小高潮
- 单元之间设置"认知过山车"（连续2章紧张→1章缓冲）
- 关键转折章需预留多视角铺垫

2. 每章需明确：
- 章节定位（角色/事件/主题等）
- 核心悬念类型（信息差/道德困境/时间压力等）
- 情感基调迁移（如从怀疑→恐惧→决绝）
- 伏笔操作（埋设/强化/回收）
- 认知颠覆强度（1-5级）

输出格式示例：
第n章 - [标题]
本章定位：[角色/事件/主题/...]
核心作用：[推进/转折/揭示/...]
悬念密度：[紧凑/渐进/爆发/...]
伏笔操作：埋设(A线索)→强化(B矛盾)...
认知颠覆：★☆☆☆☆
本章简述：[一句话概括]

第n+1章 - [标题]
本章定位：[角色/事件/主题/...]
核心作用：[推进/转折/揭示/...]
悬念密度：[紧凑/渐进/爆发/...]
伏笔操作：埋设(A线索)→强化(B矛盾)...
认知颠覆：★☆☆☆☆
本章简述：[一句话概括]

要求：
- 使用精炼语言描述，每章字数控制在100字以内。
- 合理安排节奏，确保整体悬念曲线的连贯性。
- 在生成{number_of_chapters}章前不要出现结局章节。

仅给出最终文本，不要解释任何内容。
"""


PROMPT_TEMPLATE = {
    "clarify_with_user": clarify_with_user_prompt,
    "extract_setting": extract_setting_prompt,
    "core_seed": core_seed_prompt,
    "character_dynamics": character_dynamics_prompt,
    "world_building": world_building_prompt,
    "plot_arch": plot_arch_prompt,
    "chapter_blueprint": chapter_blueprint_prompt,
    "chunked_chapter_blueprint": chunked_chapter_blueprint_prompt,
}


def apply_system_prompt_template(prompt_name, state=None):
    # Convert state to dict for template rendering
    if state is None:
        state = {}
    state_vars = {**state}
    try:
        system_prompt = PROMPT_TEMPLATE[prompt_name].format(**state_vars)
        return system_prompt
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")
