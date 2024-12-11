import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { tap } from 'rxjs/operators'
import { MailAccount } from 'src/app/data/mail-account'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class MailAccountService extends AbstractPaperlessService<MailAccount> {
  loading: boolean

  constructor(http: HttpClient) {
    super(http, 'mail_accounts')
  }

  private reload() {
    this.loading = true
    this.listAll().subscribe((r) => {
      this.mailAccounts = r.results
      this.loading = false
    })
  }

  private mailAccounts: MailAccount[] = []

  get allAccounts() {
    return this.mailAccounts
  }

  create(o: MailAccount) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: MailAccount) {
    // Remove expiration from the object before updating
    delete o.expiration
    return super.update(o).pipe(tap(() => this.reload()))
  }

  delete(o: MailAccount) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }

  test(o: MailAccount) {
    const account = Object.assign({}, o)
    delete account['set_permissions']
    return this.http.post(this.getResourceUrl() + 'test/', account)
  }

  processAccount(account: MailAccount) {
    return this.http.post(this.getResourceUrl(account.id, 'process'), {})
  }
}
