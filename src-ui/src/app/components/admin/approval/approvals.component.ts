import { Component, OnInit, OnDestroy } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { PaperlessApproval } from 'src/app/data/paperless-approval'
import { ApprovalsService } from 'src/app/services/approvals.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

@Component({
  selector: 'pngx-approvals',
  templateUrl: './approvals.component.html',
  styleUrls: ['./approvals.component.scss'],
})
export class ApprovalsComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  
  public activeTab: string
  public selectedApprovals: Set<number> = new Set()
  public togggleAll: boolean = false
  public expandedApproval: number

  public pageSize: number = 25
  public page: number = 1

  public autoRefreshInterval: any

  get dismissButtonText(): string {
    return this.selectedApprovals.size > 0
      ? $localize`Dismiss selected`
      : $localize`Dismiss all`
  }

  constructor(
    public approvalsService: ApprovalsService,
    private modalService: NgbModal,
    private readonly router: Router
  ) {
    super()
  }

  ngOnInit() {
    this.approvalsService.reload()
    this.toggleAutoRefresh()
    // console.log(approvals)
  }

  ngOnDestroy() {
    this.approvalsService.cancelPending()
    clearInterval(this.autoRefreshInterval)
  }

  dismissApproval(approval: PaperlessApproval) {
    this.dismissApprovals(approval)
  }

  dismissApprovals(approval: PaperlessApproval = undefined) {
    let approvals = approval ? new Set([approval.id]) : new Set(this.selectedApprovals.values())
    if (!approval && approvals.size == 0)
      approvals = new Set(this.approvalsService.allApprovals.map((t) => t.id))
    if (approvals.size > 1) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm Dismiss All`
      modal.componentInstance.messageBold = $localize`Dismiss all ${approvals.size} approvals?`
      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Dismiss`
      modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        modal.close()
        this.approvalsService.dismissApprovals(approvals)
        this.selectedApprovals.clear()
      })
    } else {
      this.approvalsService.dismissApprovals(approvals)
      this.selectedApprovals.clear()
    }
  }

  dismissAndGo(approval: PaperlessApproval) {
    this.dismissApproval(approval)
    this.router.navigate(['documents', approval.object_pk])
  }

  expandApproval(approval: PaperlessApproval) {
    this.expandedApproval = this.expandedApproval == approval.id ? undefined : approval.id
  }

  toggleSelected(approval: PaperlessApproval) {
    this.selectedApprovals.has(approval.id)
      ? this.selectedApprovals.delete(approval.id)
      : this.selectedApprovals.add(approval.id)
  }

  get currentApprovals(): PaperlessApproval[] {
    let approvals: PaperlessApproval[] = []
    switch (this.activeTab) {
      case 'pending':
        approvals = this.approvalsService.pendingApprovals
        break
      case 'success':
        approvals = this.approvalsService.successApprovals
        break
      case 'failure':
        approvals = this.approvalsService.failureApprovals
        break
      case 'revoked':
        approvals = this.approvalsService.revokedApprovals
        break
    }
    return approvals
  }

  toggleAll(event: PointerEvent) {
    if ((event.target as HTMLInputElement).checked) {
      this.selectedApprovals = new Set(this.currentApprovals.map((t) => t.id))
    } else {
      this.clearSelection()
    }
  }

  clearSelection() {
    this.togggleAll = false
    this.selectedApprovals.clear()
  }

  duringTabChange(navID: number) {
    this.page = 1
  }

  get activeTabLocalized(): string {
    switch (this.activeTab) {
      case 'pending':
        return $localize`pending`
      case 'success':
        return $localize`success`
      case 'failure':
        return $localize`failure`
      case 'revoked':
        return $localize`revoked`
    }
  }

  toggleAutoRefresh(): void {
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval)
      this.autoRefreshInterval = null
    } else {
      this.autoRefreshInterval = setInterval(() => {
        this.approvalsService.reload()
      }, 5000)
    }
  }
}
