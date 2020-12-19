import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { FILTER_HAS_TAG } from 'src/app/data/filter-rule-type';
import { TAG_COLOURS, PaperlessTag } from 'src/app/data/paperless-tag';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { TagEditDialogComponent } from './tag-edit-dialog/tag-edit-dialog.component';

@Component({
  selector: 'app-tag-list',
  templateUrl: './tag-list.component.html',
  styleUrls: ['./tag-list.component.scss']
})
export class TagListComponent extends GenericListComponent<PaperlessTag> {

  constructor(tagService: TagService, modalService: NgbModal,
    private router: Router,
    private list: DocumentListViewService
  ) {
    super(tagService, modalService, TagEditDialogComponent)
  }

  getColor(id) {
    return TAG_COLOURS.find(c => c.id == id)
  }

  getObjectName(object: PaperlessTag) {
    return `tag '${object.name}'`
  }

  filterDocuments(object: PaperlessTag) {
    this.list.documentListView.filter_rules = [
      {rule_type: FILTER_HAS_TAG, value: object.id.toString()}
    ]
    this.router.navigate(["documents"])
  }
}
