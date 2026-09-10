from dataclasses import dataclass, field

from channel_filter import db
from channel_filter.listener import process_channel_post
from channel_filter.matcher import AutomatonManager
from channel_filter.notifier import NotificationJob
from channel_filter.pipeline import keyword_match_stage
from channel_filter.types import ChannelPost


@dataclass
class FakeNotifier:
    jobs: list[NotificationJob] = field(default_factory=list)

    async def enqueue(self, job: NotificationJob) -> None:
        self.jobs.append(job)


async def test_matched_post_enqueues_exactly_one_job_per_matching_subscriber(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.add_keyword(conn, 1, "sale")
    await db.add_keyword(conn, 1, "discount")
    await db.get_or_create_subscriber(conn, 2)
    await db.add_keyword(conn, 2, "sale")

    manager = AutomatonManager(conn)
    await manager.build()
    stages = [keyword_match_stage(manager)]
    notifier = FakeNotifier()
    post = ChannelPost(message_id=100, text="Big sale and discount today")

    await process_channel_post(post, stages, conn, notifier, channel_username="testchan")

    assert len(notifier.jobs) == 2
    chat_ids = {job.chat_id for job in notifier.jobs}
    assert chat_ids == {1, 2}
    for job in notifier.jobs:
        assert job.text == post.text
        assert job.message_id == 100


async def test_non_matching_post_enqueues_nothing(conn):
    await db.get_or_create_subscriber(conn, 1)
    await db.add_keyword(conn, 1, "sale")

    manager = AutomatonManager(conn)
    await manager.build()
    stages = [keyword_match_stage(manager)]
    notifier = FakeNotifier()
    post = ChannelPost(message_id=101, text="nothing relevant here")

    await process_channel_post(post, stages, conn, notifier, channel_username="testchan")

    assert notifier.jobs == []
