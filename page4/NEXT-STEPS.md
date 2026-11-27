# From proposal to first Reel

| Order | Owner | Next action and completion check |
| --- | --- | --- |
| 1 | Irfan | Choose one combined Page and a name, or select the two-Page alternative. Check handle availability. For the recommended launch, create **Selak Sekejap** from the intended Facebook profile, use the BM bio in the proposal and record its new Page ID. Check the Monetization tab for this Page and record its actual status. |
| 2 | Claude + Irfan | Claude prepares an original avatar that reads at phone size, a BM cover showing the two series and two Reel-cover options using a true hero frame once available. Irfan approves the identity and the Malay voice after a blind read. Apply approved Page branding, then reopen the public Page on mobile. |
| 3 | Irfan + Claude | Irfan authorises Page-specific access in his Meta app. Request only needed scopes for listing/reading the Page, publishing and managing its comments. Keep its Page token in a private, ignored Page-specific secret store. Claude checks token validity/permissions and Graph-returned Page ID/name against step 1 without logging credentials. Wire the scheduler and commenter to that identity, fail closed on mismatch and use Asia/Kuala_Lumpur. Both current root tools default to another Page. |
| 4 | Claude chief + Codex CLI | Start with pilot 1, the detention pond. Refresh both issue sources. On an idle machine, opt Page 4 into Malay TTS checks, multilingual caption timing and full QC. Build one original scene in Python, one still and a five-second headless Blender cutaway proof. Irfan approves legibility, BM delivery and budgeted render time before the 35–60 s build. Use free quota and the existing toolchain. |
| 5 | Claude + Irfan | Finish the full Reel with timed BM captions, FFmpeg encode, custom cover and phone-size listen/watch checks. Show Irfan the exact MP4, post copy, comment and MYT slot. After release approval, schedule by Graph API and read back Page ID, video ID and scheduled time. Once live, verify Public, AI label, cover, BM captions and first comment from the Page. |

These are future launch actions. The research and scripts are ready for Irfan’s editorial review.
