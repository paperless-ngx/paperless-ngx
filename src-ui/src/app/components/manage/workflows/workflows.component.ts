import { Component, OnInit } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgbDropdownModule, NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { delay, takeUntil, tap } from 'rxjs'
import { Workflow } from 'src/app/data/workflow'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { WorkflowService } from 'src/app/services/rest/workflow.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import {
  WORKFLOW_TYPE_OPTIONS,
  WorkflowEditDialogComponent,
} from '../../common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-workflows',
  templateUrl: './workflows.component.html',
  styleUrls: ['./workflows.component.scss'],
  imports: [
    PageHeaderComponent,
    IfPermissionsDirective,
    FormsModule,
    ReactiveFormsModule,
    NgbDropdownModule,
    NgxBootstrapIconsModule,
  ],
})
export class WorkflowsComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  public workflows: Workflow[] = []

  constructor(
    private workflowService: WorkflowService,
    public permissionsService: PermissionsService,
    private modalService: NgbModal,
    private toastService: ToastService
  ) {
    super()
  }

  ngOnInit() {
    this.reload()
  }

  reload() {
    this.loading = true
    this.workflowService
      .listAll()
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        tap((r) => (this.workflows = r.results)),
        delay(100)
      )
      .subscribe(() => {
        this.show = true
        this.loading = false
      })
  }

  getTypesList(template: Workflow): string {
    return template.triggers
      .map(
        (trigger) =>
          WORKFLOW_TYPE_OPTIONS.find((t) => t.id === trigger.type).name
      )
      .join(', ')
  }

  editWorkflow(workflow: Workflow, forceCreate: boolean = false) {
    const modal = this.modalService.open(WorkflowEditDialogComponent, {
      backdrop: 'static',
      size: 'xl',
    })
    modal.componentInstance.dialogMode =
      workflow && !forceCreate ? EditDialogMode.EDIT : EditDialogMode.CREATE
    if (workflow) {
      // quick "deep" clone so original doesn't get modified
      const clone = Object.assign({}, workflow)
      clone.actions = [...workflow.actions]
      clone.triggers = [...workflow.triggers]
      modal.componentInstance.object = clone
    }
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newWorkflow) => {
        this.toastService.showInfo(
          $localize`Saved workflow "${newWorkflow.name}".`
        )
        this.workflowService.clearCache()
        this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving workflow.`, e)
      })
  }

  copyWorkflow(workflow: Workflow) {
    const clone = Object.assign({}, workflow)
    clone.id = null
    clone.name = `${workflow.name} (copy)`
    clone.actions = [
      ...workflow.actions.map((a) => {
        a.id = null
        if (a.webhook) {
          a.webhook.id = null
        }
        if (a.email) {
          a.email.id = null
        }
        return a
      }),
    ]
    clone.triggers = [
      ...workflow.triggers.map((t) => {
        t.id = null
        return t
      }),
    ]
    this.editWorkflow(clone, true)
  }

  deleteWorkflow(workflow: Workflow) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete workflow`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this workflow.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.workflowService.delete(workflow).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo(
            $localize`Deleted workflow "${workflow.name}".`
          )
          this.workflowService.clearCache()
          this.reload()
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error deleting workflow "${workflow.name}".`,
            e
          )
        },
      })
    })
  }

  toggleWorkflowEnabled(workflow: Workflow) {
    this.workflowService.patch(workflow).subscribe({
      next: () => {
        this.toastService.showInfo(
          workflow.enabled
            ? $localize`Enabled workflow "${workflow.name}"`
            : $localize`Disabled workflow "${workflow.name}"`
        )
        this.workflowService.clearCache()
        this.reload()
      },
      error: (e) => {
        this.toastService.showError(
          $localize`Error toggling workflow "${workflow.name}".`,
          e
        )
      },
    })
  }
}
