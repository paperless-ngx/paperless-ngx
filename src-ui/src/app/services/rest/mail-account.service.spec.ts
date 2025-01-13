import { HttpTestingController } from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { Subscription } from 'rxjs'
import { IMAPSecurity, MailAccountType } from 'src/app/data/mail-account'
import { environment } from 'src/environments/environment'
import { commonAbstractPaperlessServiceTests } from './abstract-paperless-service.spec'
import { MailAccountService } from './mail-account.service'

let httpTestingController: HttpTestingController
let service: MailAccountService
let subscription: Subscription
const endpoint = 'mail_accounts'
const mail_accounts = [
  {
    name: 'Mail Account',
    id: 1,
    imap_server: 'imap.example.com',
    imap_port: 443,
    imap_security: IMAPSecurity.SSL,
    username: 'user',
    password: 'pass',
    is_token: false,
    account_type: MailAccountType.IMAP,
  },
  {
    name: 'Mail Account 2',
    id: 2,
    imap_server: 'imap.example.com',
    imap_port: 443,
    imap_security: IMAPSecurity.SSL,
    username: 'user',
    password: 'pass',
    is_token: false,
    account_type: MailAccountType.IMAP,
  },
  {
    name: 'Mail Account 3',
    id: 3,
    imap_server: 'imap.example.com',
    imap_port: 443,
    imap_security: IMAPSecurity.SSL,
    username: 'user',
    password: 'pass',
    is_token: false,
    account_type: MailAccountType.IMAP,
  },
]

// run common tests
commonAbstractPaperlessServiceTests(endpoint, MailAccountService)

describe(`Additional service tests for MailAccountService`, () => {
  it('should correct api endpoint on test account', () => {
    subscription = service.test(mail_accounts[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/test/`
    )
    expect(req.request.method).toEqual('POST')
  })

  it('should support reload', () => {
    service['reload']()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
    expect(req.request.method).toEqual('GET')
    req.flush({ results: mail_accounts })
    expect(service.allAccounts).toEqual(mail_accounts)
  })

  it('should support processAccount', () => {
    subscription = service.processAccount(mail_accounts[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/${mail_accounts[0].id}/process/`
    )
    expect(req.request.method).toEqual('POST')
  })

  beforeEach(() => {
    // Dont need to setup again

    httpTestingController = TestBed.inject(HttpTestingController)
    service = TestBed.inject(MailAccountService)
  })

  afterEach(() => {
    subscription?.unsubscribe()
    httpTestingController.verify()
  })
})
