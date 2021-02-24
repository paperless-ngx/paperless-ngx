import { Component } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { DocumentService, SelectionDataItem } from 'src/app/services/rest/document.service';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { ConfirmDialogComponent } from 'src/app/components/common/confirm-dialog/confirm-dialog.component';
import { ChangedItems, FilterableDropdownSelectionModel } from '../../common/filterable-dropdown/filterable-dropdown.component';
import { ToggleableItemState } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component';
import { MatchingModel } from 'src/app/data/matching-model';
import { SettingsService, SETTINGS_KEYS } from 'src/app/services/settings.service';
import { ToastService } from 'src/app/services/toast.service';
import { saveAs } from 'file-saver';

@Component({
  selector: 'app-bulk-editor',
  templateUrl: './bulk-editor.component.html',
  styleUrls: ['./bulk-editor.component.scss']
})
export class BulkEditorComponent {

  tags: PaperlessTag[]
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  tagSelectionModel = new FilterableDropdownSelectionModel()
  correspondentSelectionModel = new FilterableDropdownSelectionModel()
  documentTypeSelectionModel = new FilterableDropdownSelectionModel()

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    public list: DocumentListViewService,
    private documentService: DocumentService,
    private modalService: NgbModal,
    private openDocumentService: OpenDocumentsService,
    private settings: SettingsService,
    private toastService: ToastService
  ) { }

  applyOnClose: boolean = this.settings.get(SETTINGS_KEYS.BULK_EDIT_APPLY_ON_CLOSE)
  showConfirmationDialogs: boolean = this.settings.get(SETTINGS_KEYS.BULK_EDIT_CONFIRMATION_DIALOGS)

  ngOnInit() {
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)
  }

  private executeBulkOperation(modal, method: string, args) {
    if (modal) {
      modal.componentInstance.buttonsEnabled = false
    }
    this.documentService.bulkEdit(Array.from(this.list.selected), method, args).subscribe(
      response => {
        this.list.reload()
        this.list.reduceSelectionToFilter()
        this.list.selected.forEach(id => {
          this.openDocumentService.refreshDocument(id)
        })
        if (modal) {
          modal.close()
        }
      }, error => {
        if (modal) {
          modal.componentInstance.buttonsEnabled = true
        }
        this.toastService.showError($localize`Error executing bulk operation: ${JSON.stringify(error.error)}`)
      }
    )
  }

  private applySelectionData(items: SelectionDataItem[], selectionModel: FilterableDropdownSelectionModel) {
    let selectionData = new Map<number, ToggleableItemState>()
    items.forEach(i => {
      if (i.document_count == this.list.selected.size) {
        selectionData.set(i.id, ToggleableItemState.Selected)
      } else if (i.document_count > 0) {
        selectionData.set(i.id, ToggleableItemState.PartiallySelected)
      }
    })
    selectionModel.init(selectionData)
  }

  openTagsDropdown() {
    this.documentService.getSelectionData(Array.from(this.list.selected)).subscribe(s => {
      this.applySelectionData(s.selected_tags, this.tagSelectionModel)
    })
  }

  openDocumentTypeDropdown() {
    this.documentService.getSelectionData(Array.from(this.list.selected)).subscribe(s => {
      this.applySelectionData(s.selected_document_types, this.documentTypeSelectionModel)
    })
  }

  openCorrespondentDropdown() {
    this.documentService.getSelectionData(Array.from(this.list.selected)).subscribe(s => {
      this.applySelectionData(s.selected_correspondents, this.correspondentSelectionModel)
    })
  }

  private _localizeList(items: MatchingModel[]) {
    if (items.length == 0) {
      return ""
    } else if (items.length == 1) {
      return $localize`"${items[0].name}"`
    } else if (items.length == 2) {
      return $localize`:This is for messages like 'modify "tag1" and "tag2"':"${items[0].name}" and "${items[1].name}"`
    } else {
      let list = items.slice(0, items.length - 1).map(i => $localize`"${i.name}"`).join($localize`:this is used to separate enumerations and should probably be a comma and a whitespace in most languages:, `)
      return $localize`:this is for messages like 'modify "tag1", "tag2" and "tag3"':${list} and "${items[items.length - 1].name}"`
    }
  }

  setTags(changedTags: ChangedItems) {
    if (changedTags.itemsToAdd.length == 0 && changedTags.itemsToRemove.length == 0) return

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
      modal.componentInstance.title = $localize`Confirm tags assignment`
      if (changedTags.itemsToAdd.length == 1 && changedTags.itemsToRemove.length == 0) {
        let tag = changedTags.itemsToAdd[0]
        modal.componentInstance.message = $localize`This operation will add the tag "${tag.name}" to ${this.list.selected.size} selected document(s).`
      } else if (changedTags.itemsToAdd.length > 1 && changedTags.itemsToRemove.length == 0) {
        modal.componentInstance.message = $localize`This operation will add the tags ${this._localizeList(changedTags.itemsToAdd)} to ${this.list.selected.size} selected document(s).`
      } else if (changedTags.itemsToAdd.length == 0 && changedTags.itemsToRemove.length == 1) {
        let tag = changedTags.itemsToRemove[0]
        modal.componentInstance.message = $localize`This operation will remove the tag "${tag.name}" from ${this.list.selected.size} selected document(s).`
      } else if (changedTags.itemsToAdd.length == 0 && changedTags.itemsToRemove.length > 1) {
        modal.componentInstance.message = $localize`This operation will remove the tags ${this._localizeList(changedTags.itemsToRemove)} from ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will add the tags ${this._localizeList(changedTags.itemsToAdd)} and remove the tags ${this._localizeList(changedTags.itemsToRemove)} on ${this.list.selected.size} selected document(s).`
      }

      modal.componentInstance.btnClass = "btn-warning"
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked.subscribe(() => {
        this.executeBulkOperation(modal, 'modify_tags', {"add_tags": changedTags.itemsToAdd.map(t => t.id), "remove_tags": changedTags.itemsToRemove.map(t => t.id)})
      })
    } else {
      this.executeBulkOperation(null, 'modify_tags', {"add_tags": changedTags.itemsToAdd.map(t => t.id), "remove_tags": changedTags.itemsToRemove.map(t => t.id)})
    }
  }

  setCorrespondents(changedCorrespondents: ChangedItems) {
    if (changedCorrespondents.itemsToAdd.length == 0 && changedCorrespondents.itemsToRemove.length == 0) return

    let correspondent = changedCorrespondents.itemsToAdd.length > 0 ? changedCorrespondents.itemsToAdd[0] : null

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
      modal.componentInstance.title = $localize`Confirm correspondent assignment`
      if (correspondent) {
        modal.componentInstance.message = $localize`This operation will assign the correspondent "${correspondent.name}" to ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will remove the correspondent from ${this.list.selected.size} selected document(s).`
      }
      modal.componentInstance.btnClass = "btn-warning"
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked.subscribe(() => {
        this.executeBulkOperation(modal, 'set_correspondent', {"correspondent": correspondent ? correspondent.id : null})
      })
    } else {
      this.executeBulkOperation(null, 'set_correspondent', {"correspondent": correspondent ? correspondent.id : null})
    }
  }

  setDocumentTypes(changedDocumentTypes: ChangedItems) {
    if (changedDocumentTypes.itemsToAdd.length == 0 && changedDocumentTypes.itemsToRemove.length == 0) return

    let documentType = changedDocumentTypes.itemsToAdd.length > 0 ? changedDocumentTypes.itemsToAdd[0] : null

    if (this.showConfirmationDialogs) {
      let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
      modal.componentInstance.title = $localize`Confirm document type assignment`
      if (documentType) {
        modal.componentInstance.message = $localize`This operation will assign the document type "${documentType.name}" to ${this.list.selected.size} selected document(s).`
      } else {
        modal.componentInstance.message = $localize`This operation will remove the document type from ${this.list.selected.size} selected document(s).`
      }
      modal.componentInstance.btnClass = "btn-warning"
      modal.componentInstance.btnCaption = $localize`Confirm`
      modal.componentInstance.confirmClicked.subscribe(() => {
        this.executeBulkOperation(modal, 'set_document_type', {"document_type": documentType ? documentType.id : null})
      })
    } else {
      this.executeBulkOperation(null, 'set_document_type', {"document_type": documentType ? documentType.id : null})
    }
  }

  applyDelete() {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.delayConfirm(5)
    modal.componentInstance.title = $localize`Delete confirm`
    modal.componentInstance.messageBold = $localize`This operation will permanently delete ${this.list.selected.size} selected document(s).`
    modal.componentInstance.message = $localize`This operation cannot be undone.`
    modal.componentInstance.btnClass = "btn-danger"
    modal.componentInstance.btnCaption = $localize`Delete document(s)`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.executeBulkOperation(modal, "delete", {})
    })
  }

  downloadSelected(content = "archive") {
    this.documentService.bulkDownload(Array.from(this.list.selected), content).subscribe((result: any) => {
      saveAs(result, 'documents.zip');
    })
  }
}
