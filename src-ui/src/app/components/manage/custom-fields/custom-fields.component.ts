import { Component, OnInit } from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, takeUntil } from 'rxjs'
import {
  DATA_TYPE_LABELS,
  PaperlessCustomField,
} from 'src/app/data/paperless-custom-field'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'

@Component({
  selector: 'pngx-custom-fields',
  templateUrl: './custom-fields.component.html',
  styleUrls: ['./custom-fields.component.scss'],
})
export class CustomFieldsComponent
  extends ComponentWithPermissions
  implements OnInit
{
  public fields: PaperlessCustomField[] = []

  private unsubscribeNotifier: Subject<any> = new Subject()
  constructor(
    private customFieldsService: CustomFieldsService,
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
    this.customFieldsService
      .listAll()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this.fields = r.results
      })
  }

  editField(field: PaperlessCustomField) {
    const modal = this.modalService.open(CustomFieldEditDialogComponent)
    modal.componentInstance.dialogMode = field
      ? EditDialogMode.EDIT
      : EditDialogMode.CREATE
    modal.componentInstance.object = field
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newField) => {
        this.toastService.showInfo($localize`Saved field "${newField.name}".`)
        this.customFieldsService.clearCache()
        this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving field.`, e)
      })
  }

  deleteField(field: PaperlessCustomField) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Confirm delete field`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete this field.`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.customFieldsService.delete(field).subscribe({
        next: () => {
          modal.close()
          this.toastService.showInfo($localize`Deleted field`)
          this.customFieldsService.clearCache()
          this.reload()
        },
        error: (e) => {
          this.toastService.showError($localize`Error deleting field.`, e)
        },
      })
    })
  }

  getDataType(field: PaperlessCustomField): string {
    return DATA_TYPE_LABELS.find((l) => l.id === field.data_type).name
  }
}
