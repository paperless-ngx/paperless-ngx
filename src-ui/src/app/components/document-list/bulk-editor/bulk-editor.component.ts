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

  private initiallySelectedTagsToggleableItems: ToggleableItem[]
  private initiallySelectedCorrespondentsToggleableItems: ToggleableItem[]
  private initiallySelectedDocumentTypesToggleableItems: ToggleableItem[]

  dropdownTypes = FilterableDropdownType

  get selectionSpansPages(): boolean {
    return this.selectedDocuments.size > this.viewDocuments.length || !Array.from(this.selectedDocuments).every(sd => this.viewDocuments.find(d => d.id == sd))
  }

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
    return tagsToggleableItems
  }

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
    return correspondentsToggleableItems
  }

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
    this.initiallySelectedTagsToggleableItems = this.tagsToggleableItems.filter(tsi => tsi.state == ToggleableItemState.Selected)
  }

  correspondentsDropdownOpen() {
    this.initiallySelectedCorrespondentsToggleableItems = this.correspondentsToggleableItems.filter(csi => csi.state == ToggleableItemState.Selected)
  }

  documentTypesDropdownOpen() {
    this.initiallySelectedDocumentTypesToggleableItems = this.documentTypesToggleableItems.filter(dtsi => dtsi.state == ToggleableItemState.Selected)
  }

  applyTags(selectedTags: PaperlessTag[]) {
    let unchanged = this.equateItemsToToggleableItems(selectedTags, this.initiallySelectedTagsToggleableItems)
    if (!unchanged) this.setTags.emit(selectedTags)
    this.initiallySelectedTagsToggleableItems = null
  }

  applyCorrespondent(selectedCorrespondents: PaperlessCorrespondent[]) {
    let unchanged = this.equateItemsToToggleableItems(selectedCorrespondents, this.initiallySelectedCorrespondentsToggleableItems)
    if (!unchanged) this.setCorrespondent.emit(selectedCorrespondents?.length > 0 ? selectedCorrespondents.shift() : null)
    this.initiallySelectedCorrespondentsToggleableItems = null
  }

  applyDocumentType(selectedDocumentTypes: PaperlessDocumentType[]) {
    let unchanged = this.equateItemsToToggleableItems(selectedDocumentTypes, this.initiallySelectedDocumentTypesToggleableItems)
    if (!unchanged) this.setDocumentType.emit(selectedDocumentTypes.length > 0 ? selectedDocumentTypes.shift() : null)
    this.initiallySelectedDocumentTypesToggleableItems = null
  }

  equateItemsToToggleableItems(items: ObjectWithId[], toggleableItems: ToggleableItem[]): boolean {
    // either both empty or all items must in toggleableItems and vice-versa
    return (toggleableItems.length == 0 && items.length == 0) ||
           (items.every(i => toggleableItems.find(si => si.item.id == i.id) !== undefined) && toggleableItems.every(si => items.find(i => i.id == si.item.id) !== undefined))
  }

  applyDelete() {
    this.delete.next()
  }
}
