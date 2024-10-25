import { HttpTestingController } from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { MailRuleService } from './mail-rule.service'
import { MailFilterAttachmentType } from 'src/app/data/mail-rule'
import { MailMetadataTitleOption } from 'src/app/data/mail-rule'
import { MailAction } from 'src/app/data/mail-rule'

let httpTestingController: HttpTestingController
let service: MailRuleService
let subscription: Subscription
const endpoint = 'mail_rules'
const mail_rules = [
  {
    name: 'Mail Rule',
    id: 1,
    account: 1,
    order: 1,
    enabled: true,
    folder: 'INBOX',
    filter_from: null,
    filter_to: null,
    filter_subject: null,
    filter_body: null,
    filter_attachment_filename_include: null,
    filter_attachment_filename_exclude: null,
    maximum_age: 30,
    attachment_type: MailFilterAttachmentType.Everything,
    action: MailAction.MarkRead,
    assign_title_from: MailMetadataTitleOption.FromSubject,
    assign_owner_from_rule: true,
  },
  {
    name: 'Mail Rule 2',
    id: 2,
    account: 1,
    order: 1,
    enabled: true,
    folder: 'INBOX',
    filter_from: null,
    filter_to: null,
    filter_subject: null,
    filter_body: null,
    filter_attachment_filename_include: null,
    filter_attachment_filename_exclude: null,
    maximum_age: 30,
    attachment_type: MailFilterAttachmentType.Everything,
    action: MailAction.Delete,
    assign_title_from: MailMetadataTitleOption.FromSubject,
    assign_owner_from_rule: true,
  },
  {
    name: 'Mail Rule 3',
    id: 3,
    account: 1,
    order: 1,
    enabled: true,
    folder: 'INBOX',
    filter_from: null,
    filter_to: null,
    filter_subject: null,
    filter_body: null,
    filter_attachment_filename_include: null,
    filter_attachment_filename_exclude: null,
    maximum_age: 30,
    attachment_type: MailFilterAttachmentType.Everything,
    action: MailAction.Flag,
    assign_title_from: MailMetadataTitleOption.FromSubject,
    assign_owner_from_rule: false,
  },
]

// run common tests
commonAbstractPaperlessServiceTests(endpoint, MailRuleService)

describe(`Additional service tests for MailRuleService`, () => {
  it('should support reload', () => {
    service['reload']()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    expect(req.request.method).toEqual('GET')
    req.flush({ results: mail_rules })
    expect(service.allRules).toEqual(mail_rules)
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(MailRuleService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })
})
