import { Component, OnInit } from '@angular/core'
import {
  NgbDropdownModule,
  NgbModal,
  NgbPaginationModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { delay, takeUntil, tap } from 'rxjs'
import { CustomField, DATA_TYPE_LABELS } from 'src/app/data/custom-field'
import {
  CustomFieldQueryLogicalOperator,
  CustomFieldQueryOperator,
} from 'src/app/data/custom-field-query'
import { FILTER_CUSTOM_FIELDS_QUERY } from 'src/app/data/filter-rule-type'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { SavedViewService } from 'src/app/services/rest/saved-view.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { PageHeaderComponent } from '../../common/page-header/page-header.component'
import { LoadingComponentWithPermissions } from '../../loading-component/loading.component'

@Component({
  selector: 'pngx-custom-fields',
  templateUrl: './custom-fields.component.html',
  styleUrls: ['./custom-fields.component.scss'],
  imports: [
    PageHeaderComponent,
    IfPermissionsDirective,
    NgbDropdownModule,
    NgbPaginationModule,
    NgxBootstrapIconsModule,
  ],
})
export class CustomFieldsComponent
  extends LoadingComponentWithPermissions
  implements OnInit
{
  public fields: CustomField[] = []

  constructor(
    private customFieldsService: CustomFieldsService,
    public permissionsService: PermissionsService,
    private modalService: NgbModal,
    private toastService: ToastService,
    private documentListViewService: DocumentListViewService,
    private settingsService: SettingsService,
    private documentService: DocumentService,
    private savedViewService: SavedViewService
  ) {
    super()
  }

  ngOnInit() {
    this.reload()
  }

  reload() {
    this.customFieldsService
      .listAll()
      .pipe(
        takeUntil(this.unsubscribeNotifier),
        tap((r) => {
          this.fields = r.results
        }),
        delay(100)
      )
      .subscribe(() => {
        this.show = true
        this.loading = false
      })
  }

  editField(field: CustomField) {
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
        this.settingsService.initializeDisplayFields()
        this.documentService.reload()
        this.reload()
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving field.`, e)
      })
  }

  deleteField(field: CustomField) {
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
          this.toastService.showInfo($localize`Deleted field "${field.name}"`)
          this.customFieldsService.clearCache()
          this.settingsService.initializeDisplayFields()
          this.documentService.reload()
          this.savedViewService.reload()
          this.reload()
        },
        error: (e) => {
          this.toastService.showError(
            $localize`Error deleting field "${field.name}".`,
            e
          )
        },
      })
    })
  }

  getDataType(field: CustomField): string {
    return DATA_TYPE_LABELS.find((l) => l.id === field.data_type).name
  }

  filterDocuments(field: CustomField) {
    this.documentListViewService.quickFilter([
      {
        rule_type: FILTER_CUSTOM_FIELDS_QUERY,
        value: JSON.stringify([
          CustomFieldQueryLogicalOperator.Or,
          [[field.id, CustomFieldQueryOperator.Exists, true]],
        ]),
      },
    ])
  }
}
