import { Component, OnInit } from '@angular/core';
import { DocumentDetailComponent } from 'src/app/components/document-detail/document-detail.component';
import { DocumentCommentService } from 'src/app/services/rest/document-comment.service';
import { PaperlessDocumentComment } from 'src/app/data/paperless-document-comment';

import { take } from 'rxjs/operators';
import { FormControl, FormGroup } from '@angular/forms';

@Component({
  selector: 'app-document-comment',
  templateUrl: './document-comment.component.html',
  styleUrls: ['./document-comment.component.scss']
})
export class DocumentCommentComponent implements OnInit {

  comments:PaperlessDocumentComment[];
  networkActive = false;
  documentId: number;
  commentForm: FormGroup = new FormGroup({
    newcomment: new FormControl('')
  })

  constructor(
    private documentDetailComponent: DocumentDetailComponent,
    private documentCommentService: DocumentCommentService,
  ) { }

  byId(index, item: PaperlessDocumentComment) {
    return item.id;
  }

  async ngOnInit(): Promise<any> {
    try {
      this.documentId = this.documentDetailComponent.documentId;
      this.comments= await this.documentCommentService.getComments(this.documentId).pipe(take(1)).toPromise();
    } catch(err){
      this.comments = [];
    }
  }

  addComment(){
    this.networkActive = true
    this.documentCommentService.addComment(this.documentId, this.commentForm.get("newcomment").value).subscribe(result => {
      this.comments = result;
      this.commentForm.get("newcomment").reset();
      this.networkActive = false;
    }, error => {
      this.networkActive = false;
    });
  }

  deleteComment(event){
    let parent = event.target.parentElement.closest('div[comment-id]');
    if(parent){
      this.documentCommentService.deleteComment(this.documentId, parseInt(parent.getAttribute("comment-id"))).subscribe(result => {
        this.comments = result;
        this.networkActive = false;
      }, error => {
        this.networkActive = false;
      });
    }
  }
}