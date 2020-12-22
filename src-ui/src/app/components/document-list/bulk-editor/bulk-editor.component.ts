import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DocumentService } from 'src/app/services/rest/document.service';
import { FilterableDropdownType } from 'src/app/components/common/filterable-dropdown/filterable-dropdown.component';
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

  @Input()
  selectedDocuments: Set<number>

  @Input()
  viewDocuments: PaperlessDocument[]

  @Output()
  selectPage = new EventEmitter()

  @Output()
  selectAll = new EventEmitter()

  @Output()
  selectNone = new EventEmitter()

  @Output()
  setTags = new EventEmitter()

  @Output()
  setCorrespondents = new EventEmitter()

  @Output()
  setDocumentTypes = new EventEmitter()

  @Output()
  delete = new EventEmitter()

  tags: PaperlessTag[]
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  private initialTagsToggleableItems: ToggleableItem[]
  private initialCorrespondentsToggleableItems: ToggleableItem[]
  private initialDocumentTypesToggleableItems: ToggleableItem[]

  dropdownTypes = FilterableDropdownType

  get selectionSpansPages(): boolean {
    return this.selectedDocuments.size > this.viewDocuments.length || !Array.from(this.selectedDocuments).every(sd => this.viewDocuments.find(d => d.id == sd))
  }

  private _tagsToggleableItems: ToggleableItem[]
  get tagsToggleableItems(): ToggleableItem[] {
    let tagsToggleableItems = []
    let selectedDocuments: PaperlessDocument[] = this.viewDocuments.filter(d => this.selectedDocuments.has(d.id))
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
    let selectedDocuments: PaperlessDocument[] = this.viewDocuments.filter(d => this.selectedDocuments.has(d.id))
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
    let selectedDocuments: PaperlessDocument[] = this.viewDocuments.filter(d => this.selectedDocuments.has(d.id))
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

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    private documentService: DocumentService
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

  applyTags(newTagsToggleableItems: ToggleableItem[]) {
    let changedTags = this.checkForChangedItems(this.initialTagsToggleableItems, newTagsToggleableItems)
    if (changedTags.itemsToAdd.length > 0 || changedTags.itemsToRemove.length > 0) this.setTags.emit(changedTags)
  }

  removeAllTags() {
    this.setTags.emit(null)
  }

  applyCorrespondent(newCorrespondentsToggleableItems: ToggleableItem[]) {
    let changedCorrespondents = this.checkForChangedItems(this.initialCorrespondentsToggleableItems, newCorrespondentsToggleableItems)
    if (changedCorrespondents.itemsToAdd.length > 0 || changedCorrespondents.itemsToRemove.length > 0) this.setCorrespondents.emit(changedCorrespondents)
  }

  removeAllCorrespondents() {
    this.setDocumentTypes.emit(null)
  }

  applyDocumentType(newDocumentTypesToggleableItems: ToggleableItem[]) {
    let changedDocumentTypes = this.checkForChangedItems(this.initialDocumentTypesToggleableItems, newDocumentTypesToggleableItems)
    if (changedDocumentTypes.itemsToAdd.length > 0 || changedDocumentTypes.itemsToRemove.length > 0) this.setDocumentTypes.emit(changedDocumentTypes)
  }

  removeAllDocumentTypes() {
    this.setDocumentTypes.emit(null)
  }

  checkForChangedItems(toggleableItemsA: ToggleableItem[], toggleableItemsB: ToggleableItem[]): ChangedItems {
    let itemsToAdd: any[] = []
    let itemsToRemove: any[] = []
    toggleableItemsA.forEach(oldItem => {
      let newItem = toggleableItemsB.find(nTTI => nTTI.item.id == oldItem.item.id)

      if (newItem.state == ToggleableItemState.Selected && (oldItem.state == ToggleableItemState.PartiallySelected || oldItem.state == ToggleableItemState.NotSelected)) itemsToAdd.push(newItem.item)
      else if (newItem.state == ToggleableItemState.NotSelected && (oldItem.state == ToggleableItemState.Selected || oldItem.state == ToggleableItemState.PartiallySelected)) itemsToRemove.push(newItem.item)
    })
    return { itemsToAdd: itemsToAdd, itemsToRemove: itemsToRemove }
  }

  applyDelete() {
    this.delete.next()
  }
}
