import { Component, EventEmitter, Input, Output } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { DocumentService } from 'src/app/services/rest/document.service';

@Component({
  selector: 'app-bulk-editor',
  templateUrl: './bulk-editor.component.html',
  styleUrls: ['./bulk-editor.component.scss']
})
export class BulkEditorComponent {

  @Input()
  documentsSelected: Set<number>

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
  removeCorrespondent = new EventEmitter()

  @Output()
  setDocumentType = new EventEmitter()

  @Output()
  removeDocumentType = new EventEmitter()

  @Output()
  addTag = new EventEmitter()

  @Output()
  removeTag = new EventEmitter()

  @Output()
  delete = new EventEmitter()

  tags: PaperlessTag[]
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[]

  get selectedTags(): PaperlessTag[] {
    let selectedTags = []
    this.allDocuments.forEach(d => {
      if (this.documentsSelected.has(d.id)) {
        if (d.tags && !d.tags.every(t => selectedTags.find(st => st.id == t) !== undefined)) d.tags$.subscribe(t => selectedTags = selectedTags.concat(t))
      }
    })
    return selectedTags
  }

  get selectedCorrespondents(): PaperlessCorrespondent[]  {
    let selectedCorrespondents = []
    this.allDocuments.forEach(d => {
      if (this.documentsSelected.has(d.id)) {
        if (d.correspondent && selectedCorrespondents.find(sc => sc.id == d.correspondent) == undefined) d.correspondent$.subscribe(c => selectedCorrespondents.push(c))
      }
    })
    return selectedCorrespondents
  }

  get selectedDocumentTypes(): PaperlessDocumentType[] {
    let selectedDocumentTypes = []
    this.allDocuments.forEach(d => {
      if (this.documentsSelected.has(d.id)) {
        if (d.document_type && selectedDocumentTypes.find(sdt => sdt.id == d.document_type) == undefined) d.document_type$.subscribe(dt => selectedDocumentTypes.push(dt))
      }
    })
    return selectedDocumentTypes
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

  applyTags(tags) {
    console.log(tags);

  }

  applyCorrespondent(correspondent) {
    console.log(correspondent);

  }

  applyDocumentType(documentType) {
    console.log(documentType);

  }
}
