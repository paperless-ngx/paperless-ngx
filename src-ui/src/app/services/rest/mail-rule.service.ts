import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { combineLatest, Observable } from 'rxjs'
import { tap } from 'rxjs/operators'
import { MailRule } from 'src/app/data/mail-rule'
import { AbstractEdocService } from './abstract-edoc-service'

@Injectable({
  providedIn: 'root',
})
export class MailRuleService extends AbstractEdocService<MailRule> {
  loading: boolean

  constructor(http: HttpClient) {
    super(http, 'mail_rules')
  }

  private reload() {
    this.loading = true
    this.listAll().subscribe((r) => {
      this.mailRules = r.results
      this.loading = false
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

  patchMany(objects: MailRule[]): Observable<MailRule[]> {
    return combineLatest(objects.map((o) => super.patch(o))).pipe(
      tap(() => this.reload())
    )
  }

  delete(o: MailRule) {
    return super.delete(o).pipe(tap(() => this.reload()))
  }
}
