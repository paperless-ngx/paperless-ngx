import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { combineLatest, Observable } from 'rxjs'
import { tap } from 'rxjs/operators'
import { PaperlessMailAccount } from 'src/app/data/paperless-mail-account'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class MailAccountService extends AbstractPaperlessService<PaperlessMailAccount> {
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

  private mailAccounts: PaperlessMailAccount[] = []

  get allAccounts() {
    return this.mailAccounts
  }

  create(o: PaperlessMailAccount) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: PaperlessMailAccount) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  patchMany(
    objects: PaperlessMailAccount[]
  ): Observable<PaperlessMailAccount[]> {
    return combineLatest(objects.map((o) => super.patch(o))).pipe(
      tap(() => this.reload())
    )
  }

  delete(o: PaperlessMailAccount) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }

  test(o: PaperlessMailAccount) {
    const account = Object.assign({}, o)
    delete account['set_permissions']
    return this.http.post(this.getResourceUrl() + 'test/', account)
  }
}
