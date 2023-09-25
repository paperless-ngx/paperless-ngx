import { Component, OnInit } from '@angular/core'
import { ConsumptionTemplateService } from 'src/app/services/rest/consumption-template.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { Subject, takeUntil } from 'rxjs'
import { PaperlessConsumptionTemplate } from 'src/app/data/paperless-consumption-template'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { ToastService } from 'src/app/services/toast.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import {
  ConsumptionTemplateEditDialogComponent,
  DOCUMENT_SOURCE_OPTIONS,
} from '../../common/edit-dialog/consumption-template-edit-dialog/consumption-template-edit-dialog.component'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'

@Component({
  selector: 'pngx-consumption-templates',
  templateUrl: './consumption-templates.component.html',
  styleUrls: ['./consumption-templates.component.scss'],
})
export class ConsumptionTemplatesComponent
  extends ComponentWithPermissions
  implements OnInit
{
  public templates: PaperlessConsumptionTemplate[] = []

  private unsubscribeNotifier: Subject<any> = new Subject()

  constructor(
    private consumptionTemplateService: ConsumptionTemplateService,
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
    this.consumptionTemplateService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this.templates = r.results
      })
  }

  getSourceList(template: PaperlessConsumptionTemplate): string {
    return template.sources
      .map((id) => DOCUMENT_SOURCE_OPTIONS.find((s) => s.id === id).name)
      .join(', ')
  }

  editTemplate(rule: PaperlessConsumptionTemplate) {
    const modal = this.modalService.open(
      ConsumptionTemplateEditDialogComponent,
      {
        backdrop: 'static',
        size: 'xl',
      }
    )
    modal.componentInstance.dialogMode = rule
      ? EditDialogMode.EDIT
      : EditDialogMode.CREATE
    modal.componentInstance.object = rule
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newTemplate) => {
        this.toastService.showInfo(
          $localize`Saved template "${newTemplate.name}".`
        )
        this.consumptionTemplateService.clearCache()
        this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving template.`, e)
      })
  }

  deleteTemplate(rule: PaperlessConsumptionTemplate) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete template`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this template.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.consumptionTemplateService.delete(rule).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo($localize`Deleted template`)
          this.consumptionTemplateService.clearCache()
          this.reload()
        },
        error: (e) => {
          this.toastService.showError($localize`Error deleting template.`, e)
        },
      })
    })
  }
}
