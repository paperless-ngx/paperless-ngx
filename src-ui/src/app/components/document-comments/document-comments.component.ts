import { Component, Input, OnInit } from '@angular/core'
import { DocumentCommentsService } from 'src/app/services/rest/document-comments.service'
import { PaperlessDocumentComment } from 'src/app/data/paperless-document-comment'
import { FormControl, FormGroup } from '@angular/forms'
import { first } from 'rxjs/operators'
import { ToastService } from 'src/app/services/toast.service'

@Component({
  selector: 'app-document-comments',
  templateUrl: './document-comments.component.html',
  styleUrls: ['./document-comments.component.scss'],
})
export class DocumentCommentsComponent implements OnInit {
  commentForm: FormGroup = new FormGroup({
    newcomment: new FormControl(''),
  })

  networkActive = false
  comments: PaperlessDocumentComment[] = []

  @Input()
  documentId: number

  constructor(
    private commentsService: DocumentCommentsService,
    private toastService: ToastService
  ) {}

  ngOnInit(): void {
    this.commentsService
      .getComments(this.documentId)
      .pipe(first())
      .subscribe((comments) => (this.comments = comments))
  }

  commentId(index, comment: PaperlessDocumentComment) {
    return comment.id
  }

  addComment() {
    this.networkActive = true
    this.commentsService
      .addComment(this.documentId, this.commentForm.get('newcomment').value)
      .subscribe({
        next: (result) => {
          this.comments = result
          this.commentForm.get('newcomment').reset()
          this.networkActive = false
        },
        error: (e) => {
          this.networkActive = false
          this.toastService.showError(
            $localize`Error saving comment: ${e.toString()}`
          )
        },
      })
  }

  deleteComment(commentId: number) {
    this.commentsService.deleteComment(this.documentId, commentId).subscribe({
      next: (result) => {
        this.comments = result
        this.networkActive = false
      },
      error: (e) => {
        this.networkActive = false
        this.toastService.showError(
          $localize`Error deleting comment: ${e.toString()}`
        )
      },
    })
  }
}
