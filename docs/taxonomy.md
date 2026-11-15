# Reuse taxonomy and transformation list

Every case in the dataset gets one value from each list. The two axes are kept separate:
reuse type is what the person who reused the media did; transformation is what
happened to the file.

## Reuse type (what was done with the media)

| Type | Definition | Example |
| --- | --- | --- |
| temporal_shift | Older media is presented as if it shows something happening now or at a different time. | A March 2023 Angers video posted in October 2026 as "Paris right now". |
| geographic_shift | Media from one place is presented as showing another place. | Footage from a protest in one country shared as a protest in France. |
| event_swap | Media from one event is presented as showing a different event. | Footage of a football celebration shared as "riots after the protest". |
| actor_misattribution | The event is real, but the wrong people are blamed or credited. | Footage of a police charge captioned as violence by "pro-Palestine terrorists". |
| scale_inflation | The size or severity of an event is exaggerated (or minimised). | A photo of a small gathering shared as "hundreds of thousands in the streets". |

**Rule for mixed cases:** if a case fits more than one type, record the main one in
`reuse_type` and put any others in `reuse_type_secondary` (may be empty).
The main type is the one the false claim depends on most.

## Transformation (what happened to the file)

| Value | Definition |
| --- | --- |
| none | The reused file is identical to the original. |
| re_encode | The file was saved again with different compression or format. |
| resize | The image or video was made larger or smaller. |
| crop | Parts of the edges were cut off. |
| mirror | The media was flipped horizontally. |
| screenshot | The reused media is a screenshot or screen recording of the original. |
| text_overlay | Text (a caption, meme text, headline) was added on top of the media. |
| logo | A logo or watermark was added. |
| ai_edit | A real photo was altered with AI tools (for example, a person or object added). Only used when the real original is identified. |

If several apply (for example crop and text overlay), use `multiple` and list them in `notes`.