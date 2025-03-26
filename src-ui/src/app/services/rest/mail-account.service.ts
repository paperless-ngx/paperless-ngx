import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { combineLatest, Observable } from 'rxjs'
import { tap } from 'rxjs/operators'
import { MailAccount } from 'src/app/data/mail-account'
import { AbstractEdocService } from './abstract-edoc-service'

@Injectable({
  providedIn: 'root',
})
export class MailAccountService extends AbstractEdocService<MailAccount> {
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
    return super.update(o).pipe(tap(() => this.reload()))
  }

  patchMany(objects: MailAccount[]): Observable<MailAccount[]> {
    return combineLatest(objects.map((o) => super.patch(o))).pipe(
      tap(() => this.reload())
    )
  }

  delete(o: MailAccount) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }

  test(o: MailAccount) {
    const account = Object.assign({}, o)
    delete account['set_permissions']
    return this.http.post(this.getResourceUrl() + 'test/', account)
  }
}
