import {
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { first, takeUntil } from 'rxjs'
import { CustomField, DATA_TYPE_LABELS } from 'src/app/data/custom-field'
import { CustomFieldInstance } from 'src/app/data/custom-field-instance'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { ToastService } from 'src/app/services/toast.service'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'
import { CustomFieldEditDialogComponent } from '../edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'

@Component({
  selector: 'pngx-custom-fields-dropdown',
  templateUrl: './custom-fields-dropdown.component.html',
  styleUrls: ['./custom-fields-dropdown.component.scss'],
})
export class CustomFieldsDropdownComponent extends LoadingComponentWithPermissions {
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

  @ViewChild('listFilterTextInput') listFilterTextInput: ElementRef
  @ViewChildren('button') buttons: QueryList<ElementRef>

  private customFields: CustomField[] = []
  private unusedFields: CustomField[] = []
  private keyboardIndex: number

  public get filteredFields(): CustomField[] {
    return this.unusedFields.filter(
      (f) =>
        !this.filterText ||
        f.name.toLowerCase().includes(this.filterText.toLowerCase())
    )
  }

  public filterText: string

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
    super()
    this.getFields()
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

  private updateUnusedFields() {
    this.unusedFields = this.customFields.filter(
      (f) => !this.existingFields?.find((e) => e.field === f.id)
    )
  }

  onOpenClose(open: boolean) {
    if (open) {
      setTimeout(() => {
        this.listFilterTextInput.nativeElement.focus()
      }, 100)
    } else {
      this.filterText = undefined
    }
    this.updateUnusedFields()
  }

  addField(field: CustomField) {
    this.added.emit(field)
    this.updateUnusedFields()
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
        setTimeout(() => this.addField(newField), 100)
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving field.`, e)
      })
  }

  getDataTypeLabel(dataType: string) {
    return DATA_TYPE_LABELS.find((l) => l.id === dataType)?.name
  }

  public listFilterEnter() {
    if (this.filteredFields.length === 1) {
      this.addField(this.filteredFields[0])
    } else if (
      this.filterText &&
      this.filteredFields.length === 0 &&
      this.canCreateFields
    ) {
      this.createField(this.filterText)
    }
  }

  private focusNextButtonItem(setFocus: boolean = true) {
    this.keyboardIndex = Math.min(
      this.buttons.length - 1,
      this.keyboardIndex + 1
    )
    if (setFocus) this.setButtonItemFocus()
  }

  focusPreviousButtonItem(setFocus: boolean = true) {
    this.keyboardIndex = Math.max(0, this.keyboardIndex - 1)
    if (setFocus) this.setButtonItemFocus()
  }

  setButtonItemFocus() {
    this.buttons.get(this.keyboardIndex)?.nativeElement.focus()
  }

  public listKeyDown(event: KeyboardEvent) {
    switch (event.key) {
      case 'ArrowDown':
        if (event.target instanceof HTMLInputElement) {
          if (
            !this.filterText ||
            event.target.selectionStart === this.filterText.length
          ) {
            this.keyboardIndex = -1
            this.focusNextButtonItem()
            event.preventDefault()
          }
        } else if (event.target instanceof HTMLButtonElement) {
          this.focusNextButtonItem()
          event.preventDefault()
        }
        break
      case 'ArrowUp':
        if (event.target instanceof HTMLButtonElement) {
          if (this.keyboardIndex === 0) {
            this.listFilterTextInput.nativeElement.focus()
          } else {
            this.focusPreviousButtonItem()
          }
          event.preventDefault()
        }
        break
      case 'Tab':
        // just track the index in case user uses arrows
        if (event.target instanceof HTMLInputElement) {
          this.keyboardIndex = 0
        } else if (event.target instanceof HTMLButtonElement) {
          if (event.shiftKey) {
            if (this.keyboardIndex > 0) {
              this.focusPreviousButtonItem(false)
            }
          } else {
            this.focusNextButtonItem(false)
          }
        }
      default:
        break
    }
  }
}
