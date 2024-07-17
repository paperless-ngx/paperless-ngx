import { Component, Input, Output, EventEmitter } from '@angular/core'
import { DocumentApprovalsService } from 'src/app/services/rest/document-approvals.service'
import { DocumentApproval } from 'src/app/data/document-approval'
import { FormControl, FormGroup } from '@angular/forms'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'
import { UserService } from 'src/app/services/rest/user.service'
import { User } from 'src/app/data/user'
import { GroupService } from 'src/app/services/rest/group.service'
import { Group } from 'src/app/data/group'

@Component({
  selector: 'pngx-document-approvals',
  templateUrl: './document-approvals.component.html',
  styleUrls: ['./document-approvals.component.scss'],
})
export class DocumentApprovalsComponent extends ComponentWithPermissions {
  approvalForm: FormGroup = new FormGroup({
    newApproval: new FormControl(''),
  })

  networkActive = false
  newApprovalError: boolean = false

  @Input()
  documentId: number

  @Input()
  approvals: DocumentApproval[] = []

  @Input()
  addDisabled: boolean = false

  @Output()
  updated: EventEmitter<DocumentApproval[]> = new EventEmitter()
  
  users: User[]
  groups: Group[]

  constructor(
    private approvalsService: DocumentApprovalsService,
    private toastService: ToastService,
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

  addApproval() {
    const approval: string = this.approvalForm.get('newApproval').value.toString().trim()
    if (approval.length == 0) {
      this.newApprovalError = true
      return
    }
    this.newApprovalError = false
    this.networkActive = true
    this.approvalsService.addApproval(this.documentId, approval).subscribe({
      next: (result) => {
        this.approvals = result
        this.approvalForm.get('newApproval').reset()
        this.networkActive = false
        this.updated.emit(this.approvals)
      },
      error: (e) => {
        this.networkActive = false
        this.toastService.showError($localize`Error saving approval`, e)
      },
    })
  }

  updateApproval(approvalId: number) {
    this.approvalsService.updateApproval(this.documentId, approvalId).subscribe({
      next: (result) => {
        this.approvals = result
        this.networkActive = false
        this.updated.emit(this.approvals)
      },
      error: (e) => {
        this.networkActive = false
        this.toastService.showError($localize`Error deleting approval`, e)
      },
    })
  }

  displayName(approval: DocumentApproval): string {
    if (!approval.submitted_by) return '';
      if (!approval.submitted_by) return ''
      const user_id = typeof approval.submitted_by === 'number' ? approval.submitted_by : approval.submitted_by
      const user = this.users?.find((u) => u.id === user_id)
      if (!user) return ''
      return user.username
  }
  
  displayGroup(approval: DocumentApproval): string {
    if (!approval.submitted_by_group) return ''
    const nameArray = this.groups?.filter(obj => approval.submitted_by_group.includes(obj.id)).map(obj => obj.name);
    return nameArray?.toString()
  }

}
