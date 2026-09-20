//
//  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
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

package chunker

import (
	"context"
	"strings"
	"testing"

	"ragflow/internal/agent/runtime"
	"ragflow/internal/common"
)

// incidentDocName is the real file name from the reported failure: the file is a
// procurement-standard PDF whose body is Q/GDW 73289.2-2026. Sliced away from the
// cover page, the table chunks kept only this name, and the answering model
// concluded the knowledge base held "only a procurement standard" rather than the
// Q/GDW body it was asked about.
const incidentDocName = "450/750V聚氯乙烯绝缘电缆采购标准+第2部分：专用技术规范_2.pdf"

const incidentDocTitle = "450/750V聚氯乙烯绝缘电缆采购标准+第2部分：专用技术规范_2"

func TestAttachDocumentContext_BindsStandardIDToEveryChunk(t *testing.T) {
	chunks := []map[string]any{
		{"text": "Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准\n第2部分：专用技术规范"},
		{"text": "表1 技术参数特性表\n型号\t芯数\t标称截面\nYJV\t3\t240"},
		{"text": "5.1 电缆结构\n导体应符合GB/T 3956-2008的规定。"},
	}
	orig := make([]string, len(chunks))
	for i, ck := range chunks {
		orig[i] = ck["text"].(string)
	}

	attachDocumentContext(chunks, incidentDocName)

	// Every chunk names the standard the document actually contains — including
	// the table chunk, which no longer looks like an unrelated procurement table.
	for i, ck := range chunks {
		text := ck["text"].(string)
		if !strings.HasPrefix(text, "[标准号: Q/GDW 73289.2-2026 | ") {
			t.Fatalf("chunk[%d] missing standard context prefix: %q", i, text)
		}
		if !strings.Contains(text, "文档: "+incidentDocTitle) {
			t.Errorf("chunk[%d] missing document title: %q", i, text)
		}
		if !strings.HasSuffix(text, orig[i]) {
			t.Errorf("chunk[%d] original text lost: %q", i, text)
		}
	}

	// The cover chunk has no heading, so its prefix carries only the fields it has.
	wantCover := "[标准号: Q/GDW 73289.2-2026 | 文档: " + incidentDocTitle + "] "
	if got := chunks[0]["text"].(string); !strings.HasPrefix(got, wantCover) {
		t.Errorf("cover chunk prefix = %q, want prefix %q", got, wantCover)
	}

	// The table chunk carries its own caption as the section.
	wantTable := "[标准号: Q/GDW 73289.2-2026 | 文档: " + incidentDocTitle + " | 章节: 表1 技术参数特性表] "
	if got := chunks[1]["text"].(string); !strings.HasPrefix(got, wantTable) {
		t.Errorf("table chunk prefix = %q, want prefix %q", got, wantTable)
	}

	// A later clause keeps its own number, not the one referenced inside its body.
	wantClause := "[标准号: Q/GDW 73289.2-2026 | 文档: " + incidentDocTitle + " | 章节: 5.1 电缆结构] "
	if got := chunks[2]["text"].(string); !strings.HasPrefix(got, wantClause) {
		t.Errorf("clause chunk prefix = %q, want prefix %q", got, wantClause)
	}
}

func TestAttachDocumentContext_LeavesOtherDocumentsByteIdentical(t *testing.T) {
	orig := []string{
		"产品使用说明书\n本产品适用于室内布线。",
		"表1 规格表\n型号\t电压\nA\t450/750V",
		"1.5 mm2 铜芯线，长期工作温度不超过70℃。",
	}
	chunks := make([]map[string]any, len(orig))
	for i, text := range orig {
		chunks[i] = map[string]any{"text": text}
	}

	attachDocumentContext(chunks, "产品说明书.pdf")

	for i, ck := range chunks {
		if got := ck["text"].(string); got != orig[i] {
			t.Errorf("chunk[%d] = %q, want unchanged %q", i, got, orig[i])
		}
	}
}

func TestAttachDocumentContext_IsIdempotent(t *testing.T) {
	chunks := []map[string]any{
		{"text": "Q/GDW 73289.2-2026\n标准正文"},
	}
	attachDocumentContext(chunks, incidentDocName)
	once := chunks[0]["text"].(string)

	attachDocumentContext(chunks, incidentDocName)

	if got := chunks[0]["text"].(string); got != once {
		t.Errorf("second pass stacked another prefix:\nfirst  = %q\nsecond = %q", once, got)
	}
	if n := strings.Count(once, contextPrefixOpen); n != 1 {
		t.Errorf("prefix occurrences = %d, want 1 in %q", n, once)
	}
}

func TestAttachDocumentContext_SkipsMediaOnlyAndMalformedChunks(t *testing.T) {
	chunks := []map[string]any{
		{"text": "Q/GDW 73289.2-2026\n标准正文"},
		{"text": "", "img_id": "picture"},
		{"text": "   \n  "},
		{"img_id": "no-text-key"},
	}
	attachDocumentContext(chunks, incidentDocName)

	if got := chunks[1]["text"].(string); got != "" {
		t.Errorf("media-only chunk text = %q, want untouched empty text", got)
	}
	if got := chunks[2]["text"].(string); got != "   \n  " {
		t.Errorf("whitespace chunk text = %q, want untouched", got)
	}
	if _, exists := chunks[3]["text"]; exists {
		t.Error("a chunk without a text key must not gain one")
	}
	if got := chunks[0]["text"].(string); !strings.HasPrefix(got, contextPrefixOpen) {
		t.Errorf("text chunk not prefixed: %q", got)
	}
}

func TestDetectStandardID(t *testing.T) {
	cases := []struct {
		name     string
		docName  string
		texts    []string
		want     string
		wantNote string
	}{
		{
			name:    "file name carries the standard number",
			docName: "Q/GDW 73289.2-2026 采购标准.pdf",
			want:    "Q/GDW 73289.2-2026",
		},
		{
			name:    "cover page carries the standard number",
			docName: "专用技术规范.pdf",
			texts:   []string{"Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准"},
			want:    "Q/GDW 73289.2-2026",
		},
		{
			name:    "national standard with a slash qualifier",
			docName: "技术规范.pdf",
			texts:   []string{"本规范依据GB/T 12706.1-2020编制。"},
			want:    "GB/T 12706.1-2020",
		},
		{
			name:    "industry standard with an em dash year separator",
			docName: "规范.pdf",
			texts:   []string{"DL/T 5221—2016"},
			want:    "DL/T 5221-2016",
		},
		{
			name:    "standard number wrapped across a cover-page line break",
			docName: "规范.pdf",
			texts:   []string{"Q/GDW\n73289.2-2026"},
			want:    "Q/GDW 73289.2-2026",
		},
		{
			// 煤炭行业标准: the file name declares no number, so the scan reaches the
			// front matter, which cites GB/T 2900.10-2001. While MT was missing from
			// the allowlist the document's own number was invisible and every chunk
			// was stamped with the cited standard instead.
			name:    "coal industry standard whose file name declares no number",
			docName: "煤炭行业标准.pdf",
			texts: []string{
				"MT/T 818.11—2009\n煤矿用电缆 第11部分：额定电压10kV及以下固定敷设电力电缆一般规定",
				"本部分参与起草单位\nGB/T 2900.10-2001 电工术语 电缆",
			},
			want: "MT/T 818.11-2009",
		},
		{
			name:    "year-less enterprise standard number",
			docName: "企标.pdf",
			texts:   []string{"Q/GDW 73289.2 专用技术规范"},
			want:    "Q/GDW 73289.2",
		},
		{
			name:     "year-less non-enterprise number is not a designation",
			docName:  "手册.pdf",
			texts:    []string{"GB 1234 见附表"},
			want:     "",
			wantNote: "a bare number with a national prefix is more likely a table value",
		},
		{
			name:     "voltage rating is not a standard number",
			docName:  "450/750V聚氯乙烯绝缘电缆采购标准.pdf",
			texts:    []string{"额定电压450/750V，用于固定敷设。"},
			want:     "",
			wantNote: "450/750V is the cable rating in the incident document",
		},
		{
			name:     "designation glued to an ASCII word is not matched",
			docName:  "report.pdf",
			texts:    []string{"GENERAL 100-2020 requirements"},
			want:     "",
			wantNote: "the inner EN must not be read as a designation",
		},
		{
			name:     "empty document",
			docName:  "",
			texts:    nil,
			want:     "",
			wantNote: "nothing to detect",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := detectStandardID(tc.docName, tc.texts); got != tc.want {
				t.Errorf("detectStandardID() = %q, want %q (%s)", got, tc.want, tc.wantNote)
			}
		})
	}
}

func TestDetectStandardID_PrefersTheEarliestNumberInReadingOrder(t *testing.T) {
	// The incident document references GB/T 3956-2008 inside a clause body; the
	// number that identifies the document comes first and must win.
	got := detectStandardID(incidentDocName, []string{
		"Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准",
		"5.1 电缆结构\n导体应符合GB/T 3956-2008的规定。",
	})
	if got != "Q/GDW 73289.2-2026" {
		t.Errorf("detectStandardID() = %q, want the document's own number", got)
	}
}

func TestDocumentSections(t *testing.T) {
	texts := []string{
		"Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准",
		"表1 技术参数特性表\n型号\t芯数",
		"YJV\t3",
		"5.1 电缆结构\n导体应符合规定。",
		"1.5 mm2 铜芯线",
		"图1所示为本标准的结构示意图。",
		"附录A 试验方法\n按GB/T 2951.11-2008执行。",
	}
	want := []string{
		"",
		"表1 技术参数特性表",
		"表1 技术参数特性表",
		"5.1 电缆结构",
		"5.1 电缆结构",
		"5.1 电缆结构",
		"附录A 试验方法",
	}
	got := documentSections(texts)
	if len(got) != len(want) {
		t.Fatalf("documentSections() returned %d entries, want %d", len(got), len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("section[%d] = %q, want %q (text %q)", i, got[i], want[i], texts[i])
		}
	}
}

func TestHeadingOf(t *testing.T) {
	cases := []struct {
		line string
		want string
	}{
		{"表1 技术参数特性表", "表1 技术参数特性表"},
		{"表 2.1  结构尺寸", "表2.1 结构尺寸"},
		{"图3 电缆截面", "图3 电缆截面"},
		{"附录A 规范性附录", "附录A 规范性附录"},
		{"第一章 总则", "第一章 总则"},
		{"第2部分：专用技术规范", "第2部分 专用技术规范"},
		{"5.1 电缆结构", "5.1 电缆结构"},
		{"# 5.1 电缆结构", "5.1 电缆结构"},
		{"2 规范性引用文件", "2 规范性引用文件"},
		{"1.5 mm2", ""},
		{"图1所示为本标准的结构示意图。", ""},
		{"450/750V聚氯乙烯绝缘电缆", ""},
		{"YJV\t3\t240", ""},
	}
	for _, tc := range cases {
		if got := headingOf(tc.line); got != tc.want {
			t.Errorf("headingOf(%q) = %q, want %q", tc.line, got, tc.want)
		}
	}
}

// TestChunkOutputDecorator_PrefixesThroughRegistry pins the wiring: the
// decorator that every registered chunker flows through binds the standard
// number to the chunk text, and the chunk id is derived from the prefixed text
// so the persisted id stays a function of the persisted content.
func TestChunkOutputDecorator_PrefixesThroughRegistry(t *testing.T) {
	const (
		docID = "doc-incident"
		text  = "表1 技术参数特性表\n型号\t芯数\nYJV\t3"
	)
	inner := &stubChunker{chunks: []map[string]any{
		{"text": "Q/GDW 73289.2-2026\n" + incidentDocName},
		{"text": text},
	}}
	decorated := &chunkOutputDecorator{inner: inner}

	// The persist path does not put `name` in the chunker's input map: the File
	// component publishes it to the run-wide Globals bag, which is where every
	// chunker variant reads it from.
	st := &runtime.CanvasState{Globals: map[string]any{"name": incidentDocName}}
	ctx := runtime.WithState(context.Background(), st)
	inputs := map[string]any{"doc_id": docID}

	out, err := decorated.Invoke(ctx, nil, inputs)
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	chunks, ok := out["chunks"].([]map[string]any)
	if !ok || len(chunks) != 2 {
		t.Fatalf("chunks = %#v, want 2 items", out["chunks"])
	}

	tableText, _ := chunks[1]["text"].(string)
	wantPrefix := "[标准号: Q/GDW 73289.2-2026 | 文档: " + incidentDocTitle + " | 章节: 表1 技术参数特性表] "
	if !strings.HasPrefix(tableText, wantPrefix) {
		t.Fatalf("table chunk text = %q, want prefix %q", tableText, wantPrefix)
	}
	if want := common.ChunkID(docID, tableText); chunks[1]["id"] != want {
		t.Errorf("chunk id = %v, want %q (id must cover the prefixed text)", chunks[1]["id"], want)
	}
}
