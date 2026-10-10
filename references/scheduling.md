# Scheduling a real agent run

Scheduling is optional and disabled by default. Profile schedule fields express preferences; they do not create a launch agent, task, cron job, or cloud automation. Only install or change a persistent schedule when the user asks for recurring execution and the target host is known.

## Three different times

1. **Source release time:** a publisher or preprint service's actual announcement schedule, verified from its official documentation when setting up a time-sensitive feed.
2. **Scheduler timezone:** the IANA timezone in which preparation and finalization should wake. A named zone handles daylight saving better than a fixed UTC offset.
3. **Report timezone:** the profile's `timezone`, used for the output date, weekend policy, and delivery deadline. A US evening can belong to the following report day in East Asia.

The shipped profile contains an example `America/New_York` preparation time of 19:00 and final time of 20:05, with a 09:30 deadline in the report timezone. Treat this as a configurable arXiv-oriented starting point, not a guarantee of publication availability. Verify the current official release calendar, holidays, delays, and the user's intended source coverage. A trigger after a usual release time is not evidence that a new batch exists.

## Manual run

Give a tool-enabled agent a prompt such as:

> Use `paper-research-daily` with my confirmed profile at the supplied path. Resolve today's date in the profile timezone, scan the library, reuse prepared evidence, search allowed sources, read and rank eligible candidates, publish the digest, and validate it. Report the actual count, the local overview link, and unresolved exceptions. Do not repeat an unchanged digest notification.

The profile path belongs in the host's local automation setup, not in a public sample or shared repository.

## Optional two-phase run

**Preparation:** scan new preexisting PDFs, deduplicate, verify publication and pool entries, download/read candidates, and save prepared evidence for the report date. Do not consume recommendation slots, set recommendation dates, or publish a final digest. Do not claim a future announcement batch was searched. A successful preparation can remain silent if that is the user's preference.

**Finalization:** load the same profile and date's prepared evidence, verify the currently public source batches, collect eligible new candidates, apply the weekday/weekend rule, publish, and validate. Report genuinely incomplete coverage or missed deadlines. On restart, reuse durable state; never treat preparation as publication.

`prepare` and `publish` are storage helpers after an agent has produced candidate records:

```text
python scripts/paper_daily.py prepare --profile ./my-profile.json --input ./prepared-candidates.json --date YYYY-MM-DD
python scripts/paper_daily.py publish --profile ./my-profile.json --input ./selected-candidates.json --date YYYY-MM-DD
python scripts/paper_daily.py validate --profile ./my-profile.json --date YYYY-MM-DD
```

They are not commands that independently search and write a digest. Do not schedule these commands alone and advertise an autonomous literature service.

## Adapter options

| Host | Integration requirement |
| --- | --- |
| Agent app with native recurring tasks | Create a recurring task in the same usable workspace, with the skill, profile, tool access, and prompt; verify the app's timezone and wake/sleep behavior |
| macOS `launchd` | Schedule an explicitly configured agent-runner executable and wrapper; use absolute executable/profile paths, a controlled working directory, and private logs |
| Windows Task Scheduler | Configure the real agent-runner executable, argument list, working directory, account permissions, timezone/DST behavior, and overlap policy |
| Other local/cloud runner | Ensure persistent library storage, private credentials, an actual agent execution command, and appropriate source/network access |

There is intentionally no universal fabricated `agent run` command: agent CLIs have different authentication, arguments, sandboxing, and noninteractive modes. Discover the installed runner's documented interface, test a manual run in the intended environment, then install the authorized schedule. Do not send institutional credentials through scheduler arguments or prompts.

## Completion and recovery

Prevent overlapping finalization runs for the same library. Give network retries a finite budget and preserve prepared work on interruption. Validate files and state after a run. If the machine was asleep or the agent could not start, report a missed run when next invoked; the skill cannot promise a deadline while its host is unavailable. Do not silently switch a user's local-only workflow to a remote service.
