import { Component } from '@angular/core';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
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
    private openDocumentService: OpenDocumentsService
  ) { }

  ngOnInit() {
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)
  }

  private executeBulkOperation(method: string, args): Observable<any> {
    return this.documentService.bulkEdit(Array.from(this.list.selected), method, args).pipe(
      tap(() => {
        this.list.reload()
        this.list.selected.forEach(id => {
          this.openDocumentService.refreshDocument(id)
        })
        this.list.selectNone()
      })
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

  setTags(changedTags: ChangedItems) {
    if (changedTags.itemsToAdd.length == 0 && changedTags.itemsToRemove.length == 0) return

    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Tags Assignment"
   
    modal.componentInstance.message = `This operation will modify some tags on all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('modify_tags', {"add_tags": changedTags.itemsToAdd.map(t => t.id), "remove_tags": changedTags.itemsToRemove.map(t => t.id)}).subscribe(
        response => {
          this.tagService.clearCache()
          modal.close()
        })
      }
    )
  }

  setCorrespondents(changedCorrespondents: ChangedItems) {
    if (changedCorrespondents.itemsToAdd.length == 0 && changedCorrespondents.itemsToRemove.length == 0) return

    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Correspondent Assignment"
    let correspondent
    let messageFragment = 'remove all correspondents from'
    if (changedCorrespondents && changedCorrespondents.itemsToAdd.length > 0) {
      correspondent = changedCorrespondents.itemsToAdd[0]
      messageFragment = `assign the correspondent ${correspondent.name} to`
    }
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_correspondent', {"correspondent": correspondent ? correspondent.id : null}).subscribe(
        response => {
          this.correspondentService.clearCache()
          modal.close()
        }
      )
    })
  }

  setDocumentTypes(changedDocumentTypes: ChangedItems) {
    if (changedDocumentTypes.itemsToAdd.length == 0 && changedDocumentTypes.itemsToRemove.length == 0) return

    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.title = "Confirm Document Type Assignment"
    let documentType
    let messageFragment = 'remove all document types from'
    if (changedDocumentTypes && changedDocumentTypes.itemsToAdd.length > 0) {
      documentType = changedDocumentTypes.itemsToAdd[0]
      messageFragment = `assign the document type ${documentType.name} to`
    }
    modal.componentInstance.message = `This operation will ${messageFragment} all ${this.list.selected.size} selected document(s).`
    modal.componentInstance.btnClass = "btn-warning"
    modal.componentInstance.btnCaption = "Confirm"
    modal.componentInstance.confirmClicked.subscribe(() => {
      this.executeBulkOperation('set_document_type', {"document_type": documentType ? documentType.id : null}).subscribe(
        response => {
          this.documentService.clearCache()
          modal.close()
        }
      )
    })
  }

  applyDelete() {
    let modal = this.modalService.open(ConfirmDialogComponent, {backdrop: 'static'})
    modal.componentInstance.delayConfirm(5)
    modal.componentInstance.title = "Delete confirm"
    modal.componentInstance.messageBold = `This operation will permanently delete all ${this.list.selected.size} selected document(s).`
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
