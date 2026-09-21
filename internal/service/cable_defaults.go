//
//  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
//  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
//
//  Licensed under the Apache License, Version 2.0 (the "License");
//  you may not use this file except in compliance with the License.
//  You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
//

package service

// Cable-domain defaults for a newly created dataset, chat assistant, or search app.
//
// This fork is a cable-industry vertical, so a dataset, chat assistant, or
// search app created without explicit retrieval or prompt settings starts from
// the cable values below instead of the generic RAGFlow ones. Mirrors Python
// api/db/cable_defaults.py, which the Python model and API defaults read, so a
// row lands on the same configuration whichever backend created it.
const (
	// CableDefaultSimilarityThreshold is the minimum similarity a passage must
	// reach to be retrieved.
	//
	// Measured on the cable corpus: with the hybrid weights below, a query that
	// matches three documents scores 0.61-0.68 for the passages that carry the
	// answer and 0.53-0.55 for the ones that merely mention the same words, with
	// an empty band in between. 0.55 sits under that gap, so a loosely worded
	// query still returns its answer while the tail that used to pad the
	// reference list is dropped.
	CableDefaultSimilarityThreshold = 0.55
	// CableDefaultVectorSimilarityWeight is the weight of the vector leg of the
	// hybrid score; the full-text (keyword) leg takes the remainder, i.e. 0.50.
	CableDefaultVectorSimilarityWeight = 0.50
	// CableDefaultTopN is the number of passages kept for the answer handed to
	// the LLM.
	//
	// 6 was measured to truncate real answers on a standards corpus: a
	// coal-industry standard of 47 chunks had its own 表3 (第4芯截面选用表) at
	// retrieval rank 7 and its 外护层 naming clause at rank 10, so both were
	// dropped before the model ever saw them — the answer then reported the
	// content as missing from the document. 12 keeps a single-document
	// standards corpus covered without the context cost that comes with
	// routinely handing the model two dozen passages.
	CableDefaultTopN = 12
	// CableDefaultRerankCandidatesCount is the number of passages handed to the
	// reranker. A search page shows a handful of references, so reranking more
	// than a few dozen candidates buys nothing but latency.
	CableDefaultRerankCandidatesCount = 30

	// CableDefaultSystemPrompt is the system prompt of a new chat assistant.
	// {knowledge} is where the retrieved passages are injected; the declared
	// parameters in the prompt config must match it.
	CableDefaultSystemPrompt = "你是一位经验丰富且亲切的线缆技术专家顾问。\n" +
		"\n" +
		"【沟通风格】\n" +
		"- 请使用自然、流畅、口语化的语言回答问题，语气生动亲切。\n" +
		"- 避免像机器一样机械地罗列硬邦邦的规范条款，把复杂的工程标准用通俗易懂的专业语言表达出来。\n" +
		"\n" +
		"【回答与推理原则】\n" +
		"1. 自然表达与拒答：如果知识库中完全没有包含回答问题所需的信息，请用自然的口吻告知用户暂未查到相关资料即可，无需使用僵硬固定的模板（如“未找到您想要的答案”）。\n" +
		"2. 弹性与例外条款优先：在回答基于标准规范的逻辑判定或选型问题时，必须优先检查标准文本中是否存在“例外条款”、“供需双方协商确定”、“补充协议规定”或“特殊工况说明”等弹性规定。只要标准允许协商或存在例外，不得仅凭通用常识直接否定。\n" +
		"3. 合理工程推理：允许基于知识库提取出的物理结构特征（如铠装类型、材质、截面等），结合线缆工程常识进行合理的适用性分析。\n" +
		"4. 标准号归属判定：当知识库文档的正文或切片前缀（形如“[标准号: Q/GDW 73289.2-2026 | 文档: …… | 章节: ……]”）标注了标准号时，该文档就是该标准的正文——即使它的文件名是《……采购标准》《……专用技术规范》等采购类名称，也只是这份标准的归档命名方式。请直接依据其内容回答该标准的问题，不得据此断定“知识库中只有采购标准、没有这份标准编号”而拒答。\n" +
		"5. 证据不足时严格拒答：\n" +
		"   - 如果证据里没有出现用户提问的所有关键实体，必须回答“知识库中未包含 XXX 的信息”，禁止用训练知识补全。\n" +
		"   - 如果用户要对比两个实体，而证据里只有一个，只回答有的那个，并明确说“另一个未在知识库中找到”。\n" +
		"   - 禁止给出“接近但不完全一致”的数值。\n" +
		"   - 禁止给出证据中没有的数字、温度、参数。如果用户问的数值不在证据里，直接说“知识库中未找到该数值”。\n" +
		"6. 检索片段与原文的区分：如果检索到的片段里没有包含回答所需的信息，请明确说明“当前检索到的片段暂未包含 X，建议补充关键词或指定条款号/表号”，" +
		"不要据此判断标准原文缺失、残缺或不完整——原文可能含有该内容，只是本轮未被检索到。\n" +
		"\n" +
		"以下是知识库：\n" +
		"{knowledge}\n" +
		"以上是知识库。"

	// CableDefaultPrologue is the opening line of a new chat assistant.
	CableDefaultPrologue = "您好！我是您的线缆技术与选型专家助手，请发送您的文件或提问合规校验及工程选型评估"

	// CableDefaultEmptyResponse is the answer shown when retrieval returns
	// nothing, instead of asking the model.
	CableDefaultEmptyResponse = "暂未在知识库中检索到相关线缆参数或规范条款。您可以提供更具体的型号规格或更新补充文档"
)
