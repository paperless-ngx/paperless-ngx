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
import { SelectableItem, SelectableItemState, FilterableDropdownType } from 'src/app/components/common/filterable-dropdown/filterable-dropdown.component';

@Component({
  selector: 'app-bulk-editor',
  templateUrl: './bulk-editor.component.html',
  styleUrls: ['./bulk-editor.component.scss']
})
export class BulkEditorComponent {

  @Input()
  selectedDocuments: Set<number>

  @Input()
  allDocuments: PaperlessDocument[]

  @Output()
  selectPage = new EventEmitter()

  @Output()
  selectAll = new EventEmitter()

  @Output()
  selectNone = new EventEmitter()

  @Output()
  setCorrespondent = new EventEmitter()

  @Output()
  setDocumentType = new EventEmitter()

  @Output()
  setTags = new EventEmitter()

  @Output()
  delete = new EventEmitter()

  tags: PaperlessTag[]
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  private _initialTagsSelectableItems: SelectableItem[]
  private _initialCorrespondentsSelectableItems: SelectableItem[]
  private _initialDocumentTypesSelectableItems: SelectableItem[]

  dropdownTypes = FilterableDropdownType

  get tagsSelectableItems(): SelectableItem[] {
    let tagsSelectableItems = []
    let selectedDocuments: PaperlessDocument[] = this.allDocuments.filter(d => this.selectedDocuments.has(d.id))
    this.tags.forEach(t => {
      let selectedDocumentsWithTag: PaperlessDocument[] = selectedDocuments.filter(d => d.tags.includes(t.id))
      let state = SelectableItemState.NotSelected
      if (selectedDocumentsWithTag.length == selectedDocuments.length) state = SelectableItemState.Selected
      else if (selectedDocumentsWithTag.length > 0 && selectedDocumentsWithTag.length < selectedDocuments.length) state = SelectableItemState.PartiallySelected
      tagsSelectableItems.push( { item: t, state: state } )
    })
    return tagsSelectableItems
  }

  get correspondentsSelectableItems(): SelectableItem[] {
    let correspondentsSelectableItems = []
    let selectedDocuments: PaperlessDocument[] = this.allDocuments.filter(d => this.selectedDocuments.has(d.id))

    this.correspondents.forEach(c => {
      let selectedDocumentsWithCorrespondent: PaperlessDocument[] = selectedDocuments.filter(d => d.correspondent == c.id)
      let state = SelectableItemState.NotSelected
      if (selectedDocumentsWithCorrespondent.length == selectedDocuments.length) state = SelectableItemState.Selected
      else if (selectedDocumentsWithCorrespondent.length > 0 && selectedDocumentsWithCorrespondent.length < selectedDocuments.length) state = SelectableItemState.PartiallySelected
      correspondentsSelectableItems.push( { item: c, state: state } )
    })
    return correspondentsSelectableItems
  }

  get documentTypesSelectableItems(): SelectableItem[] {
    let documentTypesSelectableItems = []
    let selectedDocuments: PaperlessDocument[] = this.allDocuments.filter(d => this.selectedDocuments.has(d.id))

    this.documentTypes.forEach(dt => {
      let selectedDocumentsWithDocumentType: PaperlessDocument[] = selectedDocuments.filter(d => d.document_type == dt.id)
      let state = SelectableItemState.NotSelected
      if (selectedDocumentsWithDocumentType.length == selectedDocuments.length) state = SelectableItemState.Selected
      else if (selectedDocumentsWithDocumentType.length > 0 && selectedDocumentsWithDocumentType.length < selectedDocuments.length) state = SelectableItemState.PartiallySelected
      documentTypesSelectableItems.push( { item: dt, state: state } )
    })
    return documentTypesSelectableItems
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
    this._initialTagsSelectableItems = this.tagsSelectableItems
  }

  correspondentsDropdownOpen() {
    this._initialCorrespondentsSelectableItems = this.correspondentsSelectableItems
  }

  documentTypesDropdownOpen() {
    this._initialDocumentTypesSelectableItems = this.documentTypesSelectableItems
  }

  applyTags(selectedTags: PaperlessTag[]) {
    let initiallySelectedSelectableTags = this._initialTagsSelectableItems.filter(tsi => tsi.state == SelectableItemState.Selected)
    let unchanged = this.equateItemsToSelectableItems(selectedTags, initiallySelectedSelectableTags)
    if (!unchanged) this.setTags.emit(selectedTags)
    this._initialTagsSelectableItems = null
  }

  applyCorrespondent(selectedCorrespondents: PaperlessCorrespondent[]) {
    let initiallySelectedSelectableCorrespondents = this._initialCorrespondentsSelectableItems.filter(csi => csi.state == SelectableItemState.Selected)
    let unchanged = this.equateItemsToSelectableItems(selectedCorrespondents, initiallySelectedSelectableCorrespondents)
    if (!unchanged) this.setCorrespondent.emit(selectedCorrespondents?.length > 0 ? selectedCorrespondents.shift() : null)
    this._initialCorrespondentsSelectableItems = null
  }

  applyDocumentType(selectedDocumentTypes: PaperlessDocumentType[]) {
    let initiallySelectedSelectableDocumentTypes = this._initialDocumentTypesSelectableItems.filter(dtsi => dtsi.state == SelectableItemState.Selected)
    let unchanged = this.equateItemsToSelectableItems(selectedDocumentTypes, initiallySelectedSelectableDocumentTypes)
    if (!unchanged) this.setDocumentType.emit(selectedDocumentTypes.length > 0 ? selectedDocumentTypes.shift() : null)
    this._initialDocumentTypesSelectableItems = null
  }

  equateItemsToSelectableItems(items: ObjectWithId[], selectableItems: SelectableItem[]): boolean {
    // either both empty or all items must in selectableItems and vice-versa
    return (selectableItems.length == 0 && items.length == 0) ||
           (items.every(i => selectableItems.find(si => si.item.id == i.id) !== undefined) && selectableItems.every(si => items.find(i => i.id == si.item.id) !== undefined))
  }

  applyDelete() {
    this.delete.next()
  }
}
