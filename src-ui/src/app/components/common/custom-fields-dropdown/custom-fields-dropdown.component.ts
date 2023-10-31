import {
  Component,
  EventEmitter,
  Input,
  OnDestroy,
  Output,
} from '@angular/core'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { Subject, first, takeUntil } from 'rxjs'
import { PaperlessCustomField } from 'src/app/data/paperless-custom-field'
import { PaperlessCustomFieldInstance } from 'src/app/data/paperless-custom-field-instance'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { ToastService } from 'src/app/services/toast.service'
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
  existingFields: PaperlessCustomFieldInstance[] = []

  @Output()
  added = new EventEmitter()

  private customFields: PaperlessCustomField[] = []
  public unusedFields: PaperlessCustomField[]

  public name: string

  public field: number

  private unsubscribeNotifier: Subject<any> = new Subject()

  get placeholderText(): string {
    return $localize`Choose field`
  }

  constructor(
    private customFieldsService: CustomFieldsService,
    private modalService: NgbModal,
    private toastService: ToastService
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

  private updateUnusedFields() {
    this.unusedFields = this.customFields.filter(
      (f) => !this.existingFields.find((e) => e.field.id === f.id)
    )
  }

  onOpenClose() {
    this.field = undefined
    this.updateUnusedFields()
  }

  addField() {
    this.added.emit(this.customFields.find((f) => f.id === this.field))
  }

  createField() {
    const modal = this.modalService.open(CustomFieldEditDialogComponent)
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newField) => {
        this.toastService.showInfo($localize`Saved field "${newField.name}".`)
        this.customFieldsService.clearCache()
        this.getFields()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving field.`, e)
      })
  }
}
