import {
  Component,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
} from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, first, takeUntil } from 'rxjs'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import { ToastService } from 'src/app/services/toast.service'

import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { CustomShelfEditDialogComponent } from 'src/app/components/common/edit-dialog/custom-shelf-edit-dialog/custom-shelf-edit-dialog.component'
import { CustomFields } from 'src/app/data/customfields'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { CustomFieldEditDialogComponent } from '../edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'

@Component({
  selector: 'pngx-custom-fields-dropdown',
  templateUrl: './custom-fields-dropdown.component.html',
  styleUrls: ['./custom-fields-dropdown.component.scss'],
})
export class CustomFieldsDropdownComponent implements OnDestroy {
  @Input()
  documentId: number

  @Input()
  disabled: boolean = false

  @Input()
  existingFields: CustomFieldInstance[] = []

  @Output()
  added: EventEmitter<CustomField> = new EventEmitter()

  @Output()
  created: EventEmitter<CustomField> = new EventEmitter()

  private customFields: CustomField[] = []
  public unusedFields: CustomField[]

  public name: string

  public field: number

  private unsubscribeNotifier: Subject<any> = new Subject()

  get placeholderText(): string {
    return $localize`Choose field`
  }

  get notFoundText(): string {
    return $localize`No unused fields found`
  }

  get canCreateFields(): boolean {
    return this.permissionsService.currentUserCan(
      PermissionAction.Add,
      PermissionType.CustomField
    )
  }

  constructor(
    private customFieldsService: CustomFieldsService,
    private modalService: NgbModal,
    private toastService: ToastService,
    private permissionsService: PermissionsService
  ) {
    this.getFields()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  private getFields() {
    this.customFieldsService
      .listAll()
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.customFields = result.results
        this.updateUnusedFields()
      })
  }

  public getCustomFieldFromInstance(
    instance: CustomFieldInstance
  ): CustomField {
    return this.customFields.find((f) => f.id === instance.field)
  }

  private updateUnusedFields() {
    this.unusedFields = this.customFields.filter(
      (f) =>
        !this.existingFields?.find(
          (e) => this.getCustomFieldFromInstance(e)?.id === f.id
        )
    )
  }

  onOpenClose() {
    this.field = undefined
    this.updateUnusedFields()
  }

  addField() {
    this.added.emit(this.customFields.find((f) => f.id === this.field))
  }

  createField(newName: string = null) {
    const modal = this.modalService.open(CustomFieldEditDialogComponent)
    if (newName) modal.componentInstance.object = { name: newName }
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newField) => {
        this.toastService.showInfo($localize`Saved field "${newField.name}".`)
        this.customFieldsService.clearCache()
        this.getFields()
        this.created.emit(newField)
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving field.`, e)
      })
  }
}
