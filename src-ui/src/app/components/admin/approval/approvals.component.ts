import { Component, OnInit, OnDestroy } from '@angular/core'
import { Router } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { first } from 'rxjs'
import { PaperlessApproval } from 'src/app/data/paperless-approval'
import { ApprovalsService } from 'src/app/services/approvals.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { User } from 'src/app/data/user'
import { Group } from 'src/app/data/group'
import { UserService } from 'src/app/services/rest/user.service'
import { GroupService } from 'src/app/services/rest/group.service'

@Component({
  selector: 'pngx-approvals',
  templateUrl: './approvals.component.html',
  styleUrls: ['./approvals.component.scss'],
})
export class ApprovalsComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  users: User[]
  groups: Group[]
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
  get approveButtonText(): string {
    return this.selectedApprovals.size > 0
      ? $localize`Approve selected`
      : $localize`Approval all`
  }
  
  get rejectButtonText(): string {
    return this.selectedApprovals.size > 0
      ? $localize`Reject selected`
      : $localize`Reject all`
  }
  get revokeButtonText(): string {
    return this.selectedApprovals.size > 0
      ? $localize`Revoke selected`
      : $localize`Revoke all`
  }
  constructor(
    public approvalsService: ApprovalsService,
    private modalService: NgbModal,
    private readonly router: Router,
    private userService: UserService,
    private groupService: GroupService
  ) {
    super()
    this.groupService.listAll().subscribe({
      next: (groups) => {
        this.groups = groups.results
      },
    })
    this.userService.listAll().subscribe({
      next: (users) => {
        this.users = users.results
      },
    })
  }

  ngOnInit() {
    this.approvalsService.reload()
    this.toggleAutoRefresh()
    // console.log(approvals)
  }
  
  displayName(approval: PaperlessApproval): string {
    if (!approval.submitted_by) return '';
      if (!approval.submitted_by) return ''
      const user_id = typeof approval.submitted_by === 'number' ? approval.submitted_by : approval.submitted_by
      const user = this.users?.find((u) => u.id === user_id)
      if (!user) return ''
      return user.username
  }
  
  displayGroup(approval: PaperlessApproval): string {
    if (!approval.submitted_by_group) return ''
    const nameArray = this.groups?.filter(obj => approval.submitted_by_group.includes(obj.id)).map(obj => obj.name);
    return nameArray?.toString()
  }
  ngOnDestroy() {
    this.approvalsService.cancelPending()
    clearInterval(this.autoRefreshInterval)
  }

  updateApproval(approval: PaperlessApproval, status: String) {
    this.updateApprovals(approval,status)
  }

  updateApprovals(approval: PaperlessApproval = undefined, status: String = '') {
    let approvals = approval ? new Set([approval.id]) : new Set(this.selectedApprovals.values())
    if (!approval && approvals.size == 0)
      approvals = new Set(this.approvalsService.allApprovals.map((t) => t.id))
    if (approvals.size > 1) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      switch (status){
        case "SUCCESS":
          modal.componentInstance.title = $localize`Confirm Approve All`
          modal.componentInstance.messageBold = $localize`Approve all ${approvals.size} approvals?`
          modal.componentInstance.btnClass = 'btn-warning'
          modal.componentInstance.btnCaption = $localize`Approve`
          modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
            modal.componentInstance.buttonsEnabled = false
            modal.close()
            this.approvalsService.updateApprovals(approvals,status)
            this.selectedApprovals.clear()
          })
        case "FAILURE":
          modal.componentInstance.title = $localize`Confirm Reject All`
          modal.componentInstance.messageBold = $localize`Reject all ${approvals.size} approvals?`
          modal.componentInstance.btnClass = 'btn-warning'
          modal.componentInstance.btnCaption = $localize`Reject`
          modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
            modal.componentInstance.buttonsEnabled = false
            modal.close()
            this.approvalsService.updateApprovals(approvals,status)
            this.selectedApprovals.clear()
          })
        case "REVOKE":
          modal.componentInstance.title = $localize`Confirm Revoke All`
          modal.componentInstance.messageBold = $localize`Revoke all ${approvals.size} approvals?`
          modal.componentInstance.btnClass = 'btn-warning'
          modal.componentInstance.btnCaption = $localize`Revoke`
          modal.componentInstance.confirmClicked.pipe(first()).subscribe(() => {
            modal.componentInstance.buttonsEnabled = false
            modal.close()
            this.approvalsService.updateApprovals(approvals,status)
            this.selectedApprovals.clear()
          })

      }
    } else {
      this.approvalsService.updateApprovals(approvals,status)
      this.selectedApprovals.clear()
    }
  }

  goDocument(approval: PaperlessApproval) {
    // this.updateApproval(approval)
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
