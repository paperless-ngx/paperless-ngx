import { CommonModule } from '@angular/common'
import { Component, inject, Input, OnDestroy } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import { takeUntil } from 'rxjs/operators'
import {
  DeletionRequest,
  DeletionRequestStatus,
} from 'src/app/data/deletion-request'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DeletionRequestService } from 'src/app/services/rest/deletion-request.service'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'pngx-deletion-request-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, NgxBootstrapIconsModule, CustomDatePipe],
  templateUrl: './deletion-request-detail.component.html',
})
export class DeletionRequestDetailComponent implements OnDestroy {
  @Input({ required: true }) deletionRequest!: DeletionRequest

  public DeletionRequestStatus = DeletionRequestStatus
  public activeModal = inject(NgbActiveModal)
  private deletionRequestService = inject(DeletionRequestService)
  private toastService = inject(ToastService)

  public reviewComment: string = ''
  public isProcessing: boolean = false
  private destroy$ = new Subject<void>()

  approve(): void {
    if (this.isProcessing) return

    this.isProcessing = true
    this.deletionRequestService
      .approve(this.deletionRequest.id, this.reviewComment)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (result) => {
          this.toastService.showInfo(
            $localize`Deletion request approved successfully`
          )
          this.isProcessing = false
          this.activeModal.close('approved')
        },
        error: (error) => {
          this.toastService.showError(
            $localize`Error approving deletion request`,
            error
          )
          this.isProcessing = false
        },
      })
  }

  reject(): void {
    if (this.isProcessing) return

    this.isProcessing = true
    this.deletionRequestService
      .reject(this.deletionRequest.id, this.reviewComment)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (result) => {
          this.toastService.showInfo(
            $localize`Deletion request rejected successfully`
          )
          this.isProcessing = false
          this.activeModal.close('rejected')
        },
        error: (error) => {
          this.toastService.showError(
            $localize`Error rejecting deletion request`,
            error
          )
          this.isProcessing = false
        },
      })
  }

  canModify(): boolean {
    return this.deletionRequest.status === DeletionRequestStatus.Pending
  }

  ngOnDestroy(): void {
    this.destroy$.next()
    this.destroy$.complete()
  }
}
