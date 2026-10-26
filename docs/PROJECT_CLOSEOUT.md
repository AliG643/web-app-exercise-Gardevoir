# Project 2 closeout record

Recorded on 2026-10-26. The source of course requirements is [`instructions.md`](../instructions.md). This record separates merged implementation from final acceptance; it does not certify a completed real-database test run.

## User stories and sprint boards

- [Gardevoir - Sprint 1](https://github.com/orgs/software-students-fall2026/projects/87): five core-flow stories, all implemented and merged.
- [Gardevoir - Sprint 2](https://github.com/orgs/software-students-fall2026/projects/88): seven improvement stories, all implemented and merged; final acceptance is a separate In Progress item.
- [Final acceptance and handoff #33](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/33).

The stories and boards were reconstructed during final handoff on 2026-10-26. The team confirmed this sprint grouping. Original implementation dates and review history remain in the linked PRs. These records do not replace evidence of the original standup meetings.

| User story | Owner(s) | Sprint | Implementation status | Merged PR evidence |
| --- | --- | --- | --- | --- |
| [US01: Access a campus marketplace account](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/21) | Yuyang-Ding1102 | 1 | Done | [#1](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/1), [#2](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/2), [#6](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/6) |
| [US02: Browse available items and view their details](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/22) | AliG643 | 1 | Done | [#8](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/8), [#10](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/10) |
| [US03: Publish a second-hand item](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/23) | Lyvoj | 1 | Done | [#9](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/9) |
| [US04: Manage my own listings and remove unwanted posts](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/24) | S1rius-Yang | 1 | Done | [#7](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/7), [#12](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/12) |
| [US05: Search items using combined filters](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/25) | Vent1Zzz | 1 | Done | [#3](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/3) |
| [US06: Sort results and adjust selected search filters](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/26) | Vent1Zzz | 2 | Done | [#11](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/11), [#15](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/15) |
| [US07: Keep account actions protected](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/27) | Yuyang-Ding1102 | 2 | Done | [#13](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/13) |
| [US08: Edit consistently and relist sold items](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/28) | S1rius-Yang | 2 | Done | [#14](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/14) |
| [US09: Show an optional original purchase price](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/29) | Lyvoj | 2 | Done | [#17](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/17) |
| [US10: Use the marketplace comfortably on a phone](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/30) | Yuyang-Ding1102 | 2 | Done | [#18](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/18), [#20](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/20) |
| [US11: Attach and manage a product photo](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/31) | AliG643, Yuyang-Ding1102 | 2 | Done | [#19](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/19), [#20](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/20) |
| [US12: Recover clearly from temporary database outages](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/issues/32) | Vent1Zzz | 2 | Done | [#16](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/16) |

The mobile detail-image correction and photo integration were completed in [PR #20](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/20), approved and merged on 2026-10-26 as `e000b8e`. The rejected-photo recovery issue was corrected in `be855ee`: the clear-selection control remains available after a rejected optional photo. Review of that final PR head passed 239 Python tests and nine client event-handler regression checks; the merge has the same file tree. These automated checks do not replace real MongoDB or final mobile acceptance.

## Stakeholder demo and feedback

- Date: 2026-10-21.
- Stakeholder: Vignesh, course grader.
- Completion: confirmed by Zihan on 2026-10-26; the team channel contains the original scheduling discussion and meeting link.
- Feedback, as reported by the team: the work was good overall, and additional features or polish could improve the result.
- Later merged work: [database outage recovery #16](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/16), [optional original price #17](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/17), [UI improvements #18](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/18), and [product-photo uploading #19](https://github.com/software-students-fall2026/web-app-exercise-Gardevoir/pull/19).

The feedback above is a summary, not a verbatim quotation or a claim that the stakeholder requested each specific feature. Sorting and filter controls were already implemented before the 10/21 demo.

## Meeting records

- **2026-10-14 planning meeting:** the meeting date was confirmed by Zihan on 2026-10-26. The supplied development-plan document is preserved unchanged alongside an [English planning record](meetings/2026-10-14-planning.md). It records proposed responsibilities, shared data and component contracts, integration order, and a target schedule. It does not contain attendance, meeting duration, or each member's completed work and blockers.
- **2026-10-19 class meeting:** a summary is visible in the [team Discord channel](https://discord.com/channels/1198812317274615830/1562292051804950679), forwarded on 10/20.
- **2026-10-21 stakeholder demo:** completion and feedback are recorded above; this is separate from the standup log.

The 10/14 plan originally targeted a 10/19 stakeholder demo. The actual demo date confirmed by the team is 10/21. Planned dates and tasks are not recorded as completed events. Other actual standup dates and notes still need to be collected to establish the required three meetings per week; the available records do not yet establish that frequency.

## Course requirement coverage

| Requirement | Current evidence | Remaining acceptance or confirmation |
| --- | --- | --- |
| HTML/CSS, Flask, PyMongo/MongoDB; Flask-Login for accounts | Application source and dependencies | Run against a real MongoDB instance using the documented setup |
| At least six screens | Register, login, browse, detail, publish, My items, edit, and search | Verify all eight flows from the final main branch |
| Database display, add, edit, delete, and search | Browse/detail/search, publishing, and seller management | Run the end-to-end checklist below |
| Mobile usability | Shared responsive UI and mobile detail-image correction merged in PR #20 | Recheck 320px and 390px layouts during final acceptance |
| Product vision and run instructions | README | Validate instructions from a clean environment |
| User stories as Issues and two Sprint Projects | #21–#32 and linked boards; twelve merged implementation stories | Keep final acceptance tracked separately in #33 |
| Three or more standups per week, under ten minutes each | 10/14 meeting confirmed with its planning document; 10/19 summary visible in the team channel | Collect other actual dates and notes, and confirm attendance, duration, completed work, next steps, and blockers; the available records do not establish the required frequency |
| Stakeholder feedback and final demo readiness | 10/21 demo confirmed above | Preserve actual feedback and prepare a concise final live flow |
| One shared repository, own accounts, branches and peer review | Five contributor identities and linked PR history | Confirm every member ran course setup and that course admins have repository access |
| Private real configuration and dummy env.example | .env is ignored; env.example is tracked | Confirm valid configuration is shared with teammates and admins through the course messenger |
| Final code on main and repository URL shared | PR #20 is merged; repository link is in the team channel | Merge the reviewed documentation handoff and verify final main checks |

## Final end-to-end acceptance

Use disposable test listings and two test accounts. Record the actual result, tester, date, and final commit in issue #33.

- [ ] Follow README from a clean checkout: course setup, dependencies, private environment settings, MongoDB, `db-check`, `db-init`, and `seed-demo`.
- [ ] Register, log out, log back in, and verify a protected page returns to the requested local destination.
- [ ] Publish a valid listing and confirm that its owner and active status are server controlled.
- [ ] Open it from browsing and search; verify its description, category, condition, selling price, optional original price, and contact information.
- [ ] Combine keyword, category, and inclusive price filters; test all three sorting options and filter-removal links.
- [ ] Edit the listing and confirm the updated data appears in browsing, detail, and search.
- [ ] Mark it sold, verify that public views hide it, then relist it and verify that it returns.
- [ ] Delete the disposable listing and verify that My items and public views no longer show it and old detail/edit URLs return 404.
- [ ] Use the second account to verify that another seller cannot edit, delete, mark sold, or relist the listing.
- [ ] Verify photo selection, valid upload, replacement, removal, legacy photo compatibility, and recovery after rejecting an oversized photo.
- [ ] Check a database interruption and recovery without clearing the login session or automatically repeating uncertain writes.
- [ ] Check 320px and 390px views, keyboard focus, readable errors, and responsive photo height.
- [ ] Run the final automated checks and record the tested main commit. Earlier Python checks used mongomock and do not establish real MongoDB acceptance.

## Configuration and photo handoff

Real `.env` values must remain outside Git and be shared only through the course-approved messenger access. Do not place credentials in Issues, project boards, or these documents.

MongoDB records reference uploaded photo files; cloning the repository does not transfer those files. Current main stores photos under `instance/uploads/` by default and supports an explicit `UPLOAD_FOLDER` setting. Anyone using an existing database must also have its referenced photos. Checkouts sharing a database must use accessible photo storage as described in the README; restart Flask after changing this setting.

The final submission is the team's remote main branch. The course instructions do not require an online deployment.
