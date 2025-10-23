import { Injectable } from '@angular/core'
import { tap } from 'rxjs/operators'
import { MailRule } from 'src/app/data/mail-rule'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class MailRuleService extends AbstractPaperlessService<MailRule> {
  constructor() {
    super()
    this.resourceName = 'mail_rules'
  }

  private reload() {
    this._loading = true
    this.listAll().subscribe((r) => {
      this.mailRules = r.results
      this._loading = false
    })
  }

  private mailRules: MailRule[] = []

  get allRules() {
    return this.mailRules
  }

  create(o: MailRule) {
    return super.create(o).pipe(tap(() => this.reload()))
  }

  update(o: MailRule) {
    return super.update(o).pipe(tap(() => this.reload()))
  }

  delete(o: MailRule) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
