import { Component, Input, OnDestroy, OnInit } from '@angular/core'
import { Tag } from 'src/app/data/tag'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { TagService } from 'src/app/services/rest/tag.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { NgbModal, NgbModalRef } from '@ng-bootstrap/ng-bootstrap'
import {
  DocumentService,
  SelectionDataItem,
} from 'src/app/services/rest/document.service'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { ConfirmDialogComponent } from 'src/app/components/common/confirm-dialog/confirm-dialog.component'
import {
  ChangedItems,
  FilterableDropdownSelectionModel,
} from '../../common/filterable-dropdown/filterable-dropdown.component'
import { ToggleableItemState } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component'
import { MatchingModel } from 'src/app/data/matching-model'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { saveAs } from 'file-saver'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { StoragePath } from 'src/app/data/storage-path'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { PermissionsDialogComponent } from '../../common/permissions-dialog/permissions-dialog.component'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { FormControl, FormGroup } from '@angular/forms'
import { first, map, Subject, switchMap, takeUntil } from 'rxjs'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { TagEditDialogComponent } from '../../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { DocumentTypeEditDialogComponent } from '../../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { StoragePathEditDialogComponent } from '../../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { RotateConfirmDialogComponent } from '../../common/confirm-dialog/rotate-confirm-dialog/rotate-confirm-dialog.component'
import { MergeConfirmDialogComponent } from '../../common/confirm-dialog/merge-confirm-dialog/merge-confirm-dialog.component'
import { CustomField } from 'src/app/data/custom-field'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'

@Component({
  selector: 'pngx-bulk-editor',
  templateUrl: './bulk-editor.component.html',
  styleUrls: ['./bulk-editor.component.scss'],
})
export class BulkEditorComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  tags: Tag[]
  correspondents: Correspondent[]
  documentTypes: DocumentType[]
  storagePaths: StoragePath[]
  customFields: CustomField[]

  tagSelectionModel = new FilterableDropdownSelectionModel()
  correspondentSelectionModel = new FilterableDropdownSelectionModel()
  documentTypeSelectionModel = new FilterableDropdownSelectionModel()
  storagePathsSelectionModel = new FilterableDropdownSelectionModel()
  customFieldsSelectionModel = new FilterableDropdownSelectionModel()
  tagDocumentCounts: SelectionDataItem[]
  correspondentDocumentCounts: SelectionDataItem[]
  documentTypeDocumentCounts: SelectionDataItem[]
  storagePathDocumentCounts: SelectionDataItem[]
  customFieldDocumentCounts: SelectionDataItem[]
  awaitingDownload: boolean

  unsubscribeNotifier: Subject<any> = new Subject()

  downloadForm = new FormGroup({
    downloadFileTypeArchive: new FormControl(true),
    downloadFileTypeOriginals: new FormControl(false),
    downloadUseFormatting: new FormControl(false),
  })

  @Input()
  public disabled: boolean = false

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    public list: DocumentListViewService,
    private documentService: DocumentService,
    private modalService: NgbModal,
    private openDocumentService: OpenDocumentsService,
    private settings: SettingsService,
    private toastService: ToastService,
    private storagePathService: StoragePathService,
    private customFieldService: CustomFieldsService,
    private permissionService: PermissionsService
  ) {
    super()
  }

  applyOnClose: boolean = this.settings.get(
    SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE
  )
  showConfirmationDialogs: boolean = this.settings.get(
    SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS
  )

  get userCanEditAll(): boolean {
    let canEdit: boolean = this.permissionService.currentUserCan(
      PermissionAction.Change,
      PermissionType.Document
    )
    if (!canEdit) return false

    const docs = this.list.documents.filter((d) => this.list.selected.has(d.id))
    canEdit = docs.every((d) =>
      this.permissionService.currentUserHasObjectPermissions(
        this.PermissionAction.Change,
        d
      )
    )
    return canEdit
  }

  get userOwnsAll(): boolean {
    let ownsAll: boolean = true
    const docs = this.list.documents.filter((d) => this.list.selected.has(d.id))
    ownsAll = docs.every((d) => this.permissionService.currentUserOwnsObject(d))
    return ownsAll
  }

  ngOnInit() {
    if (
      this.permissionService.currentUserCan(
        PermissionAction.View,
        PermissionType.Tag
      )
    ) {
      this.tagService
        .listAll()
        .pipe(first())
        .subscribe((result) => (this.tags = result.results))
    }
    if (
      this.permissionService.currentUserCan(
        PermissionAction.View,
        PermissionType.Correspondent
      )
    ) {
      this.correspondentService
        .listAll()
        .pipe(first())
        .subscribe((result) => (this.correspondents = result.results))
    }
    if (
      this.permissionService.currentUserCan(
        PermissionAction.View,
        PermissionType.DocumentType
      )
    ) {
      this.documentTypeService
        .listAll()
        .pipe(first())
        .subscribe((result) => (this.documentTypes = result.results))
    }
    if (
      this.permissionService.currentUserCan(
        PermissionAction.View,
        PermissionType.StoragePath
      )
    ) {
      this.storagePathService
        .listAll()
        .pipe(first())
        .subscribe((result) => (this.storagePaths = result.results))
    }
    if (
      this.permissionService.currentUserCan(
        PermissionAction.View,
        PermissionType.CustomField
      )
    ) {
      this.customFieldService
        .listAll()
        .pipe(first())
        .subscribe((result) => (this.customFields = result.results))
    }

    this.downloadForm
      .get('downloadFileTypeArchive')
      .valueChanges.pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newValue) => {
        if (!newValue) {
          this.downloadForm
            .get('downloadFileTypeOriginals')
            .patchValue(true, { emitEvent: false })
        }
      })
    this.downloadForm
      .get('downloadFileTypeOriginals')
      .valueChanges.pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((newValue) => {
        if (!newValue) {
          this.downloadForm
            .get('downloadFileTypeArchive')
            .patchValue(true, { emitEvent: false })
        }
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(this)
    this.unsubscribeNotifier.complete()
  }

  private executeBulkOperation(
    modal: NgbModalRef,
    method: string,
    args: any,
    overrideDocumentIDs?: number[]
  ) {
    if (modal) {
      modal.componentInstance.buttonsEnabled = false
    }
    this.documentService
      .bulkEdit(
        overrideDocumentIDs ?? Array.from(this.list.selected),
        method,
        args
      )
      .pipe(first())
      .subscribe({
        next: () => {
          this.list.reload()
          this.list.reduceSelectionToFilter()
          this.list.selected.forEach((id) => {
            this.openDocumentService.refreshDocument(id)
          })
          if (modal) {
            modal.close()
          }
        },
        error: (error) => {
          if (modal) {
            modal.componentInstance.buttonsEnabled = true
          }
          this.toastService.showError(
            $localize`Error executing bulk operation`,
            error
          )
        },
      })
  }

  private applySelectionData(
    items: SelectionDataItem[],
    selectionModel: FilterableDropdownSelectionModel
  ) {
    let selectionData = new Map<number, ToggleableItemState>()
    items.forEach((i) => {
      if (i.document_count == this.list.selected.size) {
        selectionData.set(i.id, ToggleableItemState.Selected)
      } else if (i.document_count > 0) {
        selectionData.set(i.id, ToggleableItemState.PartiallySelected)
      }
    })
    selectionModel.init(selectionData)
  }

  openTagsDropdown() {
    this.documentService
      .getSelectionData(Array.from(this.list.selected))
      .pipe(first())
      .subscribe((s) => {
        this.tagDocumentCounts = s.selected_tags
        this.applySelectionData(s.selected_tags, this.tagSelectionModel)
      })
  }

  openDocumentTypeDropdown() {
    this.documentService
      .getSelectionData(Array.from(this.list.selected))
      .pipe(first())
      .subscribe((s) => {
        this.documentTypeDocumentCounts = s.selected_document_types
        this.applySelectionData(
          s.selected_document_types,
          this.documentTypeSelectionModel
        )
      })
  }

  openCorrespondentDropdown() {
    this.documentService
      .getSelectionData(Array.from(this.list.selected))
      .pipe(first())
      .subscribe((s) => {
        this.correspondentDocumentCounts = s.selected_correspondents
        this.applySelectionData(
          s.selected_correspondents,
          this.correspondentSelectionModel
        )
      })
  }

  openStoragePathDropdown() {
    this.documentService
      .getSelectionData(Array.from(this.list.selected))
      .pipe(first())
      .subscribe((s) => {
        this.storagePathDocumentCounts = s.selected_storage_paths
        this.applySelectionData(
          s.selected_storage_paths,
          this.storagePathsSelectionModel
        )
      })
  }

  openCustomFieldsDropdown() {
    this.documentService
      .getSelectionData(Array.from(this.list.selected))
      .pipe(first())
      .subscribe((s) => {
        this.customFieldDocumentCounts = s.selected_custom_fields
        this.applySelectionData(
          s.selected_custom_fields,
          this.customFieldsSelectionModel
        )
      })
  }

  private _localizeList(items: MatchingModel[]) {
    if (items.length == 0) {
      return ''
    } else if (items.length == 1) {
      return $localize`"${items[0].name}"`
    } else if (items.length == 2) {
      return $localize`:This is for messages like 'modify "tag1" and "tag2"':"${items[0].name}" and "${items[1].name}"`
    } else {
      let list = items
        .slice(0, items.length - 1)
        .map((i) => $localize`"${i.name}"`)
        .join(
          $localize`:this is used to separate enumerations and should probably be a comma and a whitespace in most languages:, `
        )
      return $localize`:this is for messages like 'modify "tag1", "tag2" and "tag3"':${list} and "${
        items[items.length - 1].name
      }"`
    }
  }

  setTags(changedTags: ChangedItems) {
    if (
      changedTags.itemsToAdd.length == 0 &&
      changedTags.itemsToRemove.length == 0
    )
      return

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm tags assignment`
      if (
        changedTags.itemsToAdd.length == 1 &&
        changedTags.itemsToRemove.length == 0
      ) {
        let tag = changedTags.itemsToAdd[0]
        modal.componentInstance.message = $localize`This operation will add the tag "${tag.name}" to ${this.list.selected.size} selected document(s).`
      } else if (
        changedTags.itemsToAdd.length > 1 &&
        changedTags.itemsToRemove.length == 0
      ) {
        modal.componentInstance.message = $localize`This operation will add the tags ${this._localizeList(
          changedTags.itemsToAdd
        )} to ${this.list.selected.size} selected document(s).`
      } else if (
        changedTags.itemsToAdd.length == 0 &&
        changedTags.itemsToRemove.length == 1
      ) {
        let tag = changedTags.itemsToRemove[0]
        modal.componentInstance.message = $localize`This operation will remove the tag "${tag.name}" from ${this.list.selected.size} selected document(s).`
      } else if (
        changedTags.itemsToAdd.length == 0 &&
        changedTags.itemsToRemove.length > 1
      ) {
        modal.componentInstance.message = $localize`This operation will remove the tags ${this._localizeList(
          changedTags.itemsToRemove
        )} from ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will add the tags ${this._localizeList(
          changedTags.itemsToAdd
        )} and remove the tags ${this._localizeList(
          changedTags.itemsToRemove
        )} on ${this.list.selected.size} selected document(s).`
      }

      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe(() => {
          this.executeBulkOperation(modal, 'modify_tags', {
            add_tags: changedTags.itemsToAdd.map((t) => t.id),
            remove_tags: changedTags.itemsToRemove.map((t) => t.id),
          })
        })
    } else {
      this.executeBulkOperation(null, 'modify_tags', {
        add_tags: changedTags.itemsToAdd.map((t) => t.id),
        remove_tags: changedTags.itemsToRemove.map((t) => t.id),
      })
    }
  }

  setCorrespondents(changedCorrespondents: ChangedItems) {
    if (
      changedCorrespondents.itemsToAdd.length == 0 &&
      changedCorrespondents.itemsToRemove.length == 0
    )
      return

    let correspondent =
      changedCorrespondents.itemsToAdd.length > 0
        ? changedCorrespondents.itemsToAdd[0]
        : null

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm correspondent assignment`
      if (correspondent) {
        modal.componentInstance.message = $localize`This operation will assign the correspondent "${correspondent.name}" to ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will remove the correspondent from ${this.list.selected.size} selected document(s).`
      }
      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe(() => {
          this.executeBulkOperation(modal, 'set_correspondent', {
            correspondent: correspondent ? correspondent.id : null,
          })
        })
    } else {
      this.executeBulkOperation(null, 'set_correspondent', {
        correspondent: correspondent ? correspondent.id : null,
      })
    }
  }

  setDocumentTypes(changedDocumentTypes: ChangedItems) {
    if (
      changedDocumentTypes.itemsToAdd.length == 0 &&
      changedDocumentTypes.itemsToRemove.length == 0
    )
      return

    let documentType =
      changedDocumentTypes.itemsToAdd.length > 0
        ? changedDocumentTypes.itemsToAdd[0]
        : null

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm document type assignment`
      if (documentType) {
        modal.componentInstance.message = $localize`This operation will assign the document type "${documentType.name}" to ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will remove the document type from ${this.list.selected.size} selected document(s).`
      }
      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe(() => {
          this.executeBulkOperation(modal, 'set_document_type', {
            document_type: documentType ? documentType.id : null,
          })
        })
    } else {
      this.executeBulkOperation(null, 'set_document_type', {
        document_type: documentType ? documentType.id : null,
      })
    }
  }

  setStoragePaths(changedDocumentPaths: ChangedItems) {
    if (
      changedDocumentPaths.itemsToAdd.length == 0 &&
      changedDocumentPaths.itemsToRemove.length == 0
    )
      return

    let storagePath =
      changedDocumentPaths.itemsToAdd.length > 0
        ? changedDocumentPaths.itemsToAdd[0]
        : null

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm storage path assignment`
      if (storagePath) {
        modal.componentInstance.message = $localize`This operation will assign the storage path "${storagePath.name}" to ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will remove the storage path from ${this.list.selected.size} selected document(s).`
      }
      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe(() => {
          this.executeBulkOperation(modal, 'set_storage_path', {
            storage_path: storagePath ? storagePath.id : null,
          })
        })
    } else {
      this.executeBulkOperation(null, 'set_storage_path', {
        storage_path: storagePath ? storagePath.id : null,
      })
    }
  }

  setCustomFields(changedCustomFields: ChangedItems) {
    if (
      changedCustomFields.itemsToAdd.length == 0 &&
      changedCustomFields.itemsToRemove.length == 0
    )
      return

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm custom field assignment`
      if (
        changedCustomFields.itemsToAdd.length == 1 &&
        changedCustomFields.itemsToRemove.length == 0
      ) {
        let customField = changedCustomFields.itemsToAdd[0]
        modal.componentInstance.message = $localize`This operation will assign the custom field "${customField.name}" to ${this.list.selected.size} selected document(s).`
      } else if (
        changedCustomFields.itemsToAdd.length > 1 &&
        changedCustomFields.itemsToRemove.length == 0
      ) {
        modal.componentInstance.message = $localize`This operation will assign the custom fields ${this._localizeList(
          changedCustomFields.itemsToAdd
        )} to ${this.list.selected.size} selected document(s).`
      } else if (
        changedCustomFields.itemsToAdd.length == 0 &&
        changedCustomFields.itemsToRemove.length == 1
      ) {
        let customField = changedCustomFields.itemsToRemove[0]
        modal.componentInstance.message = $localize`This operation will remove the custom field "${customField.name}" from ${this.list.selected.size} selected document(s).`
      } else if (
        changedCustomFields.itemsToAdd.length == 0 &&
        changedCustomFields.itemsToRemove.length > 1
      ) {
        modal.componentInstance.message = $localize`This operation will remove the custom fields ${this._localizeList(
          changedCustomFields.itemsToRemove
        )} from ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will assign the custom fields ${this._localizeList(
          changedCustomFields.itemsToAdd
        )} and remove the custom fields ${this._localizeList(
          changedCustomFields.itemsToRemove
        )} on ${this.list.selected.size} selected document(s).`
      }

      modal.componentInstance.btnClass = 'btn-warning'
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe(() => {
          this.executeBulkOperation(modal, 'modify_custom_fields', {
            add_custom_fields: changedCustomFields.itemsToAdd.map((f) => f.id),
            remove_custom_fields: changedCustomFields.itemsToRemove.map(
              (f) => f.id
            ),
          })
        })
    } else {
      this.executeBulkOperation(null, 'modify_custom_fields', {
        add_custom_fields: changedCustomFields.itemsToAdd.map((f) => f.id),
        remove_custom_fields: changedCustomFields.itemsToRemove.map(
          (f) => f.id
        ),
      })
    }
  }

  createTag(name: string) {
    let modal = this.modalService.open(TagEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    modal.componentInstance.object = { name }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newTag) => {
          return this.tagService
            .listAll()
            .pipe(map((tags) => ({ newTag, tags })))
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newTag, tags }) => {
        this.tags = tags.results
        this.tagSelectionModel.toggle(newTag.id)
      })
  }

  createCorrespondent(name: string) {
    let modal = this.modalService.open(CorrespondentEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    modal.componentInstance.object = { name }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newCorrespondent) => {
          return this.correspondentService
            .listAll()
            .pipe(
              map((correspondents) => ({ newCorrespondent, correspondents }))
            )
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newCorrespondent, correspondents }) => {
        this.correspondents = correspondents.results
        this.correspondentSelectionModel.toggle(newCorrespondent.id)
      })
  }

  createDocumentType(name: string) {
    let modal = this.modalService.open(DocumentTypeEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    modal.componentInstance.object = { name }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newDocumentType) => {
          return this.documentTypeService
            .listAll()
            .pipe(map((documentTypes) => ({ newDocumentType, documentTypes })))
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newDocumentType, documentTypes }) => {
        this.documentTypes = documentTypes.results
        this.documentTypeSelectionModel.toggle(newDocumentType.id)
      })
  }

  createStoragePath(name: string) {
    let modal = this.modalService.open(StoragePathEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    modal.componentInstance.object = { name }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newStoragePath) => {
          return this.storagePathService
            .listAll()
            .pipe(map((storagePaths) => ({ newStoragePath, storagePaths })))
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newStoragePath, storagePaths }) => {
        this.storagePaths = storagePaths.results
        this.storagePathsSelectionModel.toggle(newStoragePath.id)
      })
  }

  createCustomField(name: string) {
    let modal = this.modalService.open(CustomFieldEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.dialogMode = EditDialogMode.CREATE
    modal.componentInstance.object = { name }
    modal.componentInstance.succeeded
      .pipe(
        switchMap((newCustomField) => {
          return this.customFieldService
            .listAll()
            .pipe(map((customFields) => ({ newCustomField, customFields })))
        })
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(({ newCustomField, customFields }) => {
        this.customFields = customFields.results
        this.customFieldsSelectionModel.toggle(newCustomField.id)
      })
  }

  applyDelete() {
    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {
        backdrop: 'static',
      })
      modal.componentInstance.title = $localize`Confirm`
      modal.componentInstance.messageBold = $localize`Move ${this.list.selected.size} selected document(s) to the trash?`
      modal.componentInstance.message = $localize`Documents can be restored prior to permanent deletion.`
      modal.componentInstance.btnClass = 'btn-danger'
      modal.componentInstance.btnCaption = $localize`Move to trash`
      modal.componentInstance.confirmClicked
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe(() => {
          modal.componentInstance.buttonsEnabled = false
          this.executeBulkOperation(modal, 'delete', {})
        })
    } else {
      this.executeBulkOperation(null, 'delete', {})
    }
  }

  downloadSelected() {
    this.awaitingDownload = true
    let downloadFileType: string =
      this.downloadForm.get('downloadFileTypeArchive').value &&
      this.downloadForm.get('downloadFileTypeOriginals').value
        ? 'both'
        : this.downloadForm.get('downloadFileTypeArchive').value
          ? 'archive'
          : 'originals'
    this.documentService
      .bulkDownload(
        Array.from(this.list.selected),
        downloadFileType,
        this.downloadForm.get('downloadUseFormatting').value
      )
      .pipe(first())
      .subscribe((result: any) => {
        saveAs(result, 'documents.zip')
        this.awaitingDownload = false
      })
  }

  reprocessSelected() {
    let modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Reprocess confirm`
    modal.componentInstance.messageBold = $localize`This operation will permanently recreate the archive files for ${this.list.selected.size} selected document(s).`
    modal.componentInstance.message = $localize`The archive files will be re-generated with the current settings.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Proceed`
    modal.componentInstance.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        modal.componentInstance.buttonsEnabled = false
        this.executeBulkOperation(modal, 'reprocess', {})
      })
  }

  setPermissions() {
    let modal = this.modalService.open(PermissionsDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.confirmClicked.subscribe(
      ({ permissions, merge }) => {
        modal.componentInstance.buttonsEnabled = false
        this.executeBulkOperation(modal, 'set_permissions', {
          ...permissions,
          merge,
        })
      }
    )
  }

  rotateSelected() {
    let modal = this.modalService.open(RotateConfirmDialogComponent, {
      backdrop: 'static',
      size: 'lg',
    })
    const rotateDialog = modal.componentInstance as RotateConfirmDialogComponent
    rotateDialog.title = $localize`Rotate confirm`
    rotateDialog.messageBold = $localize`This operation will permanently rotate the original version of ${this.list.selected.size} document(s).`
    rotateDialog.btnClass = 'btn-danger'
    rotateDialog.btnCaption = $localize`Proceed`
    rotateDialog.documentID = Array.from(this.list.selected)[0]
    rotateDialog.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        rotateDialog.buttonsEnabled = false
        this.executeBulkOperation(modal, 'rotate', {
          degrees: rotateDialog.degrees,
        })
      })
  }

  mergeSelected() {
    let modal = this.modalService.open(MergeConfirmDialogComponent, {
      backdrop: 'static',
    })
    const mergeDialog = modal.componentInstance as MergeConfirmDialogComponent
    mergeDialog.title = $localize`Merge confirm`
    mergeDialog.messageBold = $localize`This operation will merge ${this.list.selected.size} selected documents into a new document.`
    mergeDialog.btnCaption = $localize`Proceed`
    mergeDialog.documentIDs = Array.from(this.list.selected)
    mergeDialog.confirmClicked
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        const args = {}
        if (mergeDialog.metadataDocumentID > -1) {
          args['metadata_document_id'] = mergeDialog.metadataDocumentID
        }
        if (mergeDialog.deleteOriginals) {
          args['delete_originals'] = true
        }
        mergeDialog.buttonsEnabled = false
        this.executeBulkOperation(modal, 'merge', args, mergeDialog.documentIDs)
        this.toastService.showInfo(
          $localize`Merged document will be queued for consumption.`
        )
      })
  }
}
