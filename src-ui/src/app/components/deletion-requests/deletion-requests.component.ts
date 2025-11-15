import { CommonModule } from '@angular/common'
import { Component, OnInit, OnDestroy, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import {
  NgbModal,
  NgbNavModule,
  NgbPaginationModule,
  NgbTooltipModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, takeUntil } from 'rxjs'
import {
  DeletionRequest,
  DeletionRequestStatus,
} from 'src/app/data/deletion-request'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DeletionRequestService } from 'src/app/services/rest/deletion-request.service'
import { ToastService } from 'src/app/services/toast.service'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../loading-component/loading.component'
import { DeletionRequestDetailComponent } from './deletion-request-detail/deletion-request-detail.component'

@Component({
  selector: 'pngx-deletion-requests',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NgbNavModule,
    NgbPaginationModule,
    NgbTooltipModule,
    NgxBootstrapIconsModule,
    PageHeaderComponent,
    CustomDatePipe,
  ],
  templateUrl: './deletion-requests.component.html',
})
export class DeletionRequestsComponent
  extends LoadingComponentWithPermissions
  implements OnInit, OnDestroy
{
  public DeletionRequestStatus = DeletionRequestStatus

  public deletionRequestService = inject(DeletionRequestService)
  private modalService = inject(NgbModal)
  private toastService = inject(ToastService)
  protected unsubscribeNotifier: Subject<void> = new Subject()

  public deletionRequests: DeletionRequest[] = []
  public filteredRequests: DeletionRequest[] = []
  public activeTab: DeletionRequestStatus = DeletionRequestStatus.Pending
  public page: number = 1
  public pageSize: number = 25
  public collectionSize: number = 0

  ngOnInit(): void {
    this.loadDeletionRequests()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  loadDeletionRequests(): void {
    this.deletionRequestService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => {
          this.deletionRequests = result.results
          this.filterByStatus()
        },
        error: (error) => {
          this.toastService.showError(
            $localize`Error loading deletion requests`,
            error
          )
        },
      })
  }

  filterByStatus(): void {
    this.filteredRequests = this.deletionRequests.filter(
      (req) => req.status === this.activeTab
    )
    this.collectionSize = this.filteredRequests.length
    this.page = 1
  }

  onTabChange(status: DeletionRequestStatus): void {
    this.activeTab = status
    this.filterByStatus()
  }

  viewDetails(request: DeletionRequest): void {
    const modalRef = this.modalService.open(DeletionRequestDetailComponent, {
      size: 'xl',
      backdrop: 'static',
    })
    modalRef.componentInstance.deletionRequest = request
    modalRef.result.then(
      (result) => {
        if (result === 'approved' || result === 'rejected') {
          this.loadDeletionRequests()
        }
      },
      () => {
        // Modal dismissed
      }
    )
  }

  getStatusBadgeClass(status: DeletionRequestStatus): string {
    switch (status) {
      case DeletionRequestStatus.Pending:
        return 'bg-warning text-dark'
      case DeletionRequestStatus.Approved:
        return 'bg-success'
      case DeletionRequestStatus.Rejected:
        return 'bg-danger'
      case DeletionRequestStatus.Completed:
        return 'bg-info'
      case DeletionRequestStatus.Cancelled:
        return 'bg-secondary'
      default:
        return 'bg-secondary'
    }
  }

  getPendingCount(): number {
    return this.deletionRequests.filter(
      (req) => req.status === DeletionRequestStatus.Pending
    ).length
  }

  getStatusCount(status: DeletionRequestStatus): number {
    return this.deletionRequests.filter((req) => req.status === status).length
  }
}
