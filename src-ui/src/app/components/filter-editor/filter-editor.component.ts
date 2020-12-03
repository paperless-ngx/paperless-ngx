import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FilterRule } from 'src/app/data/filter-rule';
import { FilterRuleType, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';


@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit {

  constructor(private documentTypeService: DocumentTypeService, private tagService: TagService, private correspondentService: CorrespondentService) { }

  @Output()
  clear = new EventEmitter()

  @Input()
  filterRules: FilterRule[] = []

  @Output()
  apply = new EventEmitter()

  selectedRuleType: FilterRuleType = FILTER_RULE_TYPES[0]

  correspondents: PaperlessCorrespondent[] = []
  tags: PaperlessTag[] = []
  documentTypes: PaperlessDocumentType[] = []

  newRuleClicked() {
    this.filterRules.push({type: this.selectedRuleType, value: null})
    this.selectedRuleType = this.getRuleTypes().length > 0 ? this.getRuleTypes()[0] : null
  }

  removeRuleClicked(rule) {
    let index = this.filterRules.findIndex(r => r == rule)
    if (index > -1) {
      this.filterRules.splice(index, 1)
    }
  }

  applyClicked() {
    this.apply.next()
  }

  clearClicked() {
    this.filterRules.splice(0,this.filterRules.length)
    this.clear.next()
  }

  ngOnInit(): void {
    this.correspondentService.listAll().subscribe(result => {this.correspondents = result.results})
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)
  }

  getRuleTypes() {
    return FILTER_RULE_TYPES.filter(rt => rt.multi || !this.filterRules.find(r => r.type == rt))
  }

}
