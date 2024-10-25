import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
} from '@angular/core'
import { FormGroup, FormControl, FormArray } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import {
  DATA_TYPE_LABELS,
  CustomField,
  CustomFieldDataType,
} from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { EditDialogComponent, EditDialogMode } from '../edit-dialog.component'
import { Subject, takeUntil } from 'rxjs'

@Component({
  selector: 'pngx-custom-field-edit-dialog',
  templateUrl: './custom-field-edit-dialog.component.html',
  styleUrls: ['./custom-field-edit-dialog.component.scss'],
})
export class CustomFieldEditDialogComponent
  extends EditDialogComponent<CustomField>
  implements OnInit, AfterViewInit, OnDestroy
{
  CustomFieldDataType = CustomFieldDataType

  @ViewChildren('selectOption')
  private selectOptionInputs: QueryList<ElementRef>

  private unsubscribeNotifier: Subject<any> = new Subject()

  private get selectOptions(): FormArray {
    return (this.objectForm.controls.extra_data as FormGroup).controls
      .select_options as FormArray
  }

  constructor(
    service: CustomFieldsService,
    activeModal: NgbActiveModal,
    userService: UserService,
    settingsService: SettingsService
  ) {
    super(service, activeModal, userService, settingsService)
  }

  ngOnInit(): void {
    super.ngOnInit()
    if (this.typeFieldDisabled) {
      this.objectForm.get('data_type').disable()
    }
    if (this.object?.data_type === CustomFieldDataType.Select) {
      this.selectOptions.clear()
      this.object.extra_data.select_options.forEach((option) =>
        this.selectOptions.push(new FormControl(option))
      )
    }
  }

  ngAfterViewInit(): void {
    this.selectOptionInputs.changes
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.selectOptionInputs.last?.nativeElement.focus()
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  getCreateTitle() {
    return $localize`Create new custom field`
  }

  getEditTitle() {
    return $localize`Edit custom field`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(null),
      data_type: new FormControl(null),
      extra_data: new FormGroup({
        select_options: new FormArray([new FormControl(null)]),
        default_currency: new FormControl(null),
      }),
    })
  }

  getDataTypes() {
    return DATA_TYPE_LABELS
  }

  get typeFieldDisabled(): boolean {
    return this.dialogMode === EditDialogMode.EDIT
  }

  public addSelectOption() {
    this.selectOptions.push(new FormControl(''))
  }

  public removeSelectOption(index: number) {
    this.selectOptions.removeAt(index)
  }
}
