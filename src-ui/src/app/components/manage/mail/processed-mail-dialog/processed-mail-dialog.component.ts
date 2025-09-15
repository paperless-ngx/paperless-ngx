import { SlicePipe } from '@angular/common'
import { Component, inject, Input, OnInit } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbActiveModal,
  NgbPagination,
  NgbPopoverModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { ConfirmButtonComponent } from 'src/app/components/common/confirm-button/confirm-button.component'
import { MailRule } from 'src/app/data/mail-rule'
import { ProcessedMail } from 'src/app/data/processed-mail'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { ProcessedMailService } from 'src/app/services/rest/processed-mail.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-processed-mail-dialog',
  imports: [
    ConfirmButtonComponent,
    CustomDatePipe,
    NgbPagination,
    NgbPopoverModule,
    NgbTooltipModule,
    NgxBootstrapIconsModule,
    FormsModule,
    ReactiveFormsModule,
    SlicePipe,
  ],
  templateUrl: './processed-mail-dialog.component.html',
  styleUrl: './processed-mail-dialog.component.scss',
})
export class ProcessedMailDialogComponent implements OnInit {
  private readonly activeModal = inject(NgbActiveModal)
  private readonly processedMailService = inject(ProcessedMailService)
  private readonly toastService = inject(ToastService)

  public processedMails: ProcessedMail[] = []

  public loading: boolean = true
  public toggleAllEnabled: boolean = false
  public readonly selectedMailIds: Set<number> = new Set<number>()

  public page: number = 1

  @Input() rule: MailRule

  ngOnInit(): void {
    this.loadProcessedMails()
  }

  public close() {
    this.activeModal.close()
  }

  private loadProcessedMails(): void {
    this.loading = true
    this.clearSelection()
    this.processedMailService
      .list(this.page, 50, 'processed_at', true, { rule: this.rule.id })
      .subscribe((result) => {
        this.processedMails = result.results
        this.loading = false
      })
  }

  public deleteSelected(): void {
    this.processedMailService
      .bulk_delete(Array.from(this.selectedMailIds))
      .subscribe(() => {
        this.toastService.showInfo($localize`Processed mail(s) deleted`)
        this.loadProcessedMails()
      })
  }

  public toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedMailIds.clear()
      this.processedMails.forEach((mail) => this.selectedMailIds.add(mail.id))
    } else {
      this.clearSelection()
    }
  }

  public clearSelection() {
    this.toggleAllEnabled = false
    this.selectedMailIds.clear()
  }

  public toggleSelected(mail: ProcessedMail) {
    this.selectedMailIds.has(mail.id)
      ? this.selectedMailIds.delete(mail.id)
      : this.selectedMailIds.add(mail.id)
  }
}
