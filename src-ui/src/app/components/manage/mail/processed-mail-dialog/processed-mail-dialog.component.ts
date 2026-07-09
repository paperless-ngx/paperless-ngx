import { SlicePipe } from '@angular/common'
import { Component, inject, Input, OnInit, signal } from '@angular/core'
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

  private readonly ruleSignal = signal<MailRule>(undefined)
  readonly processedMails = signal<ProcessedMail[]>([])
  readonly loading = signal(true)
  readonly toggleAllEnabled = signal(false)
  readonly selectedMailIds = signal<Set<number>>(new Set())

  public page: number = 1

  @Input()
  get rule(): MailRule {
    return this.ruleSignal()
  }

  set rule(rule: MailRule) {
    this.ruleSignal.set(rule)
  }

  ngOnInit(): void {
    this.loadProcessedMails()
  }

  public close() {
    this.activeModal.close()
  }

  private loadProcessedMails(): void {
    this.loading.set(true)
    this.clearSelection()
    this.processedMailService
      .list(this.page, 50, 'processed_at', true, { rule: this.rule.id })
      .subscribe((result) => {
        this.processedMails.set(result.results)
        this.loading.set(false)
      })
  }

  public deleteSelected(): void {
    this.processedMailService
      .bulk_delete(Array.from(this.selectedMailIds()))
      .subscribe(() => {
        this.toastService.showInfo($localize`Processed mail(s) deleted`)
        this.loadProcessedMails()
      })
  }

  public toggleAll(event: PointerEvent) {
    const selectedMailIds = new Set<number>()
    if ((event.target as HTMLInputElement).checked) {
      this.processedMails().forEach((mail) => selectedMailIds.add(mail.id))
      this.selectedMailIds.set(selectedMailIds)
    } else {
      this.clearSelection()
    }
  }

  public clearSelection() {
    this.toggleAllEnabled.set(false)
    this.selectedMailIds.set(new Set())
  }

  public toggleSelected(mail: ProcessedMail) {
    const selectedMailIds = new Set(this.selectedMailIds())
    selectedMailIds.has(mail.id)
      ? selectedMailIds.delete(mail.id)
      : selectedMailIds.add(mail.id)
    this.selectedMailIds.set(selectedMailIds)
  }
}
