import { Injectable } from '@angular/core'
import { ProcessedMail } from 'src/app/data/processed-mail'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class ProcessedMailService extends AbstractPaperlessService<ProcessedMail> {
  constructor() {
    super()
    this.resourceName = 'processed_mail'
  }

  public bulk_delete(mailIds: number[]) {
    return this.http.post(`${this.getResourceUrl()}bulk_delete/`, {
      mail_ids: mailIds,
    })
  }
}
