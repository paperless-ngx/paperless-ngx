import { Component, EventEmitter, Input, Output } from '@angular/core';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { DocumentService } from 'src/app/services/rest/document.service';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';
import { FilterableDropdownType } from 'src/app/components/common/filterable-dropdown/filterable-dropdown.component';
import { ConfirmDialogComponent } from 'src/app/components/common/confirm-dialog/confirm-dialog.component';
import { ToggleableItem, ToggleableItemState } from 'src/app/components/common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component';

export interface ChangedItems {
  itemsToAdd: any[],
  itemsToRemove: any[]
}

@Component({
  selector: 'app-bulk-editor',
  templateUrl: './bulk-editor.component.html',
  styleUrls: ['./bulk-editor.component.scss']
})
export class BulkEditorComponent {

  tags: PaperlessTag[]
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  private initialTagsToggleableItems: ToggleableItem[]
  private initialCorrespondentsToggleableItems: ToggleableItem[]
  private initialDocumentTypesToggleableItems: ToggleableItem[]

  dropdownTypes = FilterableDropdownType

  get selectionSpansPages(): boolean {
    return this.documentList.selected.size > this.documentList.documents.length || !Array.from(this.documentList.selected).every(sd => this.documentList.documents.find(d => d.id == sd))
  }

  private _tagsToggleableItems: ToggleableItem[]
  get tagsToggleableItems(): ToggleableItem[] {
    let tagsToggleableItems = []
    let selectedDocuments: PaperlessDocument[] = this.documentList.documents.filter(d => this.documentList.selected.has(d.id))
    if (this.selectionSpansPages) selectedDocuments = []

    this.tags?.forEach(t => {
      let selectedDocumentsWithTag: PaperlessDocument[] = selectedDocuments.filter(d => d.tags.includes(t.id))
      let state = ToggleableItemState.NotSelected
      if (selectedDocuments.length > 0 && selectedDocumentsWithTag.length == selectedDocuments.length) state = ToggleableItemState.Selected
      else if (selectedDocumentsWithTag.length > 0 && selectedDocumentsWithTag.length < selectedDocuments.length) state = ToggleableItemState.PartiallySelected
      tagsToggleableItems.push({item: t, state: state, count: selectedDocumentsWithTag.length})
    })
    this._tagsToggleableItems = tagsToggleableItems
    return tagsToggleableItems
  }

  private _correspondentsToggleableItems: ToggleableItem[]
  get correspondentsToggleableItems(): ToggleableItem[] {
    let correspondentsToggleableItems = []
    let selectedDocuments: PaperlessDocument[] = this.documentList.documents.filter(d => this.documentList.selected.has(d.id))
    if (this.selectionSpansPages) selectedDocuments = []

    this.correspondents?.forEach(c => {
      let selectedDocumentsWithCorrespondent: PaperlessDocument[] = selectedDocuments.filter(d => d.correspondent == c.id)
      let state = ToggleableItemState.NotSelected
      if (selectedDocuments.length > 0 && selectedDocumentsWithCorrespondent.length == selectedDocuments.length) state = ToggleableItemState.Selected
      else if (selectedDocumentsWithCorrespondent.length > 0 && selectedDocumentsWithCorrespondent.length < selectedDocuments.length) state = ToggleableItemState.PartiallySelected
      correspondentsToggleableItems.push({item: c, state: state, count: selectedDocumentsWithCorrespondent.length})
    })
    this._correspondentsToggleableItems = correspondentsToggleableItems
    return correspondentsToggleableItems
  }

  private _documentTypesToggleableItems: ToggleableItem[]
  get documentTypesToggleableItems(): ToggleableItem[] {
    let documentTypesToggleableItems = []
    let selectedDocuments: PaperlessDocument[] = this.documentList.documents.filter(d => this.documentList.selected.has(d.id))
    if (this.selectionSpansPages) selectedDocuments = []

    this.documentTypes?.forEach(dt => {
      let selectedDocumentsWithDocumentType: PaperlessDocument[] = selectedDocuments.filter(d => d.document_type == dt.id)
      let state = ToggleableItemState.NotSelected
      if (selectedDocuments.length > 0 && selectedDocumentsWithDocumentType.length == selectedDocuments.length) state = ToggleableItemState.Selected
      else if (selectedDocumentsWithDocumentType.length > 0 && selectedDocumentsWithDocumentType.length < selectedDocuments.length) state = ToggleableItemState.PartiallySelected
      documentTypesToggleableItems.push({item: dt, state: state, count: selectedDocumentsWithDocumentType.length})
    })
    this._documentTypesToggleableItems = documentTypesToggleableItems
    return documentTypesToggleableItems
  }

  get documentList(): DocumentListViewService {
    return this.documentListViewService
  }

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    private documentListViewService: DocumentListViewService,
    private documentService: DocumentService,
    private modalService: NgbModal,
    private openDocumentService: OpenDocumentsService
  ) { }

  ngOnInit() {
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)
  }

  tagsDropdownOpen() {
    this.initialTagsToggleableItems = this._tagsToggleableItems
  }

  correspondentsDropdownOpen() {
    this.initialCorrespondentsToggleableItems = this._correspondentsToggleableItems
  }

  documentTypesDropdownOpen() {
    this.initialDocumentTypesToggleableItems = this._documentTypesToggleableItems
  }

  private checkForChangedItems(toggleableItemsA: ToggleableItem[], toggleableItemsB: ToggleableItem[]): ChangedItems {
    let itemsToAdd: any[] = []
    let itemsToRemove: any[] = []
    toggleableItemsA.forEach(oldItem => {
      let newItem = toggleableItemsB.find(nTTI => nTTI.item.id == oldItem.item.id)

      if (newItem.state == ToggleableItemState.Selected && (oldItem.state == ToggleableItemState.PartiallySelected || oldItem.state == ToggleableItemState.NotSelected)) itemsToAdd.push(newItem.item)
      else if (newItem.state == ToggleableItemState.NotSelected && (oldItem.state == ToggleableItemState.Selected || oldItem.state == ToggleableItemState.PartiallySelected)) itemsToRemove.push(newItem.item)
    })
    return { itemsToAdd: itemsToAdd, itemsToRemove: itemsToRemove }
  }

  private executeBulkOperation(method: string, args): Observable<any> {
    return this.documentService.bulkEdit(Array.from(this.documentList.selected), method, args).pipe(
      tap(() => {
        this.documentList.reload()
        this.documentList.selected.forEach(id => {
          this.openDocumentService.refreshDocument(id)
        })
        this.documentList.selectNone()
      })
    )
  }

  setTags(newTagsToggleableItems: ToggleableItem[]) {
    let changedTags: ChangedItems
    if (newTagsToggleableItems) {
      changedTags = this.checkForChangedItems(this.initialTagsToggleableItems, newTagsToggleableItems)
      if (changedTags.itemsToAdd.length == 0 && changedTags.itemsToRemove.length == 0) return
    }

    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Tags Assignment"
    let action = 'set_tags'
    let tags
    let messageFragment = ''
    let both = changedTags && changedTags.itemsToAdd.length > 0 && changedTags.itemsToRemove.length > 0
    if (!changedTags) {
      messageFragment = `remove all tags from`
    } else {
      if (changedTags.itemsToAdd.length > 0) {
        tags = changedTags.itemsToAdd
        messageFragment = `assign the tag(s) ${changedTags.itemsToAdd.map(t => t.name).join(', ')} to`
      }
      if (changedTags.itemsToRemove.length > 0) {
        if (!both) {
          action = 'remove_tags'
          tags = changedTags.itemsToRemove
        } else {
          messageFragment += ' and '
        }
        messageFragment += `remove the tag(s) ${changedTags.itemsToRemove.map(t => t.name).join(', ')} from`
      }
    }
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.documentList.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      // TODO: API endpoints for add/remove multiple tags
      this.executeBulkOperation(action, {"tags": tags ? tags.map(t => t.id) : null}).subscribe(
        response => {
          if (!both) modal.close()
          else {
            this.executeBulkOperation('remove_tags', {"tags": changedTags.itemsToRemove.map(t => t.id)}).subscribe(
              response => {
                modal.close()
              })
          }
        }
      )
    })
  }

  setCorrespondents(newCorrespondentsToggleableItems: ToggleableItem[]) {
    let changedCorrespondents: ChangedItems
    if (newCorrespondentsToggleableItems) {
      changedCorrespondents = this.checkForChangedItems(this.initialCorrespondentsToggleableItems, newCorrespondentsToggleableItems)
      if (changedCorrespondents.itemsToAdd.length == 0 && changedCorrespondents.itemsToRemove.length == 0) return
    }

    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Correspondent Assignment"
    let correspondent
    let messageFragment = 'remove all correspondents from'
    if (changedCorrespondents && changedCorrespondents.itemsToAdd.length > 0) {
      correspondent = changedCorrespondents.itemsToAdd[0]
      messageFragment = `assign the correspondent ${correspondent.name} to`
    }
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.documentList.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_correspondent', {"correspondent": correspondent ? correspondent.id : null}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  setDocumentTypes(newDocumentTypesToggleableItems: ToggleableItem[]) {
    let changedDocumentTypes: ChangedItems
    if (newDocumentTypesToggleableItems) {
      changedDocumentTypes = this.checkForChangedItems(this.initialDocumentTypesToggleableItems, newDocumentTypesToggleableItems)
      if (changedDocumentTypes.itemsToAdd.length == 0 && changedDocumentTypes.itemsToRemove.length == 0) return
    }

    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Document Type Assignment"
    let documentType
    let messageFragment = 'remove all document types from'
    if (changedDocumentTypes && changedDocumentTypes.itemsToAdd.length > 0) {
      documentType = changedDocumentTypes.itemsToAdd[0]
      messageFragment = `assign the document type ${documentType.name} to`
    }
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.documentList.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_document_type', {"document_type": documentType ? documentType.id : null}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }

  applyDelete() {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.delayConfirm(5)
    modal.componentInstance.title = "Delete confirm"
    modal.componentInstance.messageBold = `This operation will permanently delete all ${this.documentList.selected.size} selected document(s).`
    modal.componentInstance.message = `This operation cannot be undone.`
    modal.componentInstance.btnClass = "btn-danger"
    modal.componentInstance.btnCaption = "Delete document(s)"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation("delete", {}).subscribe(
        response => {
          modal.close()
        }
      )
    })
  }
}
