import { HttpTestingController } from '@angular/common/http/testing'
import { Subscription } from 'rxjs'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { commonAbstractEdocServiceTests } from './abstract-edoc-service.spec'
import { MailAccountService } from './mail-account.service'
import { IMAPSecurity } from 'src/app/data/mail-account'

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
  },
]

// run common tests
commonAbstractEdocServiceTests(endpoint, MailAccountService)

describe(`Additional service tests for MailAccountService`, () => {
  it('should correct api endpoint on test account', () => {
    subscription = service.test(mail_accounts[0]).subscribe()
    const req = httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/test/`
    )
    expect(req.request.method).toEqual('POST')
  })

  it('should support patchMany', () => {
    subscription = service.patchMany(mail_accounts).subscribe()
    mail_accounts.forEach((mail_account) => {
      const req = httpTestingController.expectOne(
        `${environment.apiBaseUrl}${endpoint}/${mail_account.id}/`
      )
      expect(req.request.method).toEqual('PATCH')
      req.flush(mail_account)
    })
    httpTestingController.expectOne(
      `${environment.apiBaseUrl}${endpoint}/?page=1&page_size=100000`
    )
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
