from paperless_video.content import assemble_video_content


def test_transcript_only():
    assert assemble_video_content("transcript", "全转写", None) == "全转写"


def test_summary_only():
    assert assemble_video_content("summary", "全转写", "短摘要") == "短摘要"


def test_both():
    out = assemble_video_content("both", "全转写", "短摘要")
    assert out.startswith("【摘要】")
    assert "短摘要" in out
    assert "【转写】" in out
    assert "全转写" in out
