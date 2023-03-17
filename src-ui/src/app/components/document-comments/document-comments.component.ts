import { Component, Input, Output, EventEmitter } from '@angular/core'
import { DocumentCommentsService } from 'src/app/services/rest/document-comments.service'
import { PaperlessDocumentComment } from 'src/app/data/paperless-document-comment'
import { FormControl, FormGroup } from '@angular/forms'
import { first } from 'rxjs/operators'
import { ToastService } from 'src/app/services/toast.service'
import { ComponentWithPermissions } from '../with-permissions/with-permissions.component'

@Component({
  selector: 'app-document-comments',
  templateUrl: './document-comments.component.html',
  styleUrls: ['./document-comments.component.scss'],
})
export class DocumentCommentsComponent extends ComponentWithPermissions {
  commentForm: FormGroup = new FormGroup({
    newComment: new FormControl(''),
  })

  networkActive = false
  newCommentError: boolean = false

  @Input()
  documentId: number

  @Input()
  comments: PaperlessDocumentComment[] = []

  @Output()
  updated: EventEmitter<PaperlessDocumentComment[]> = new EventEmitter()

  constructor(
    private commentsService: DocumentCommentsService,
    private toastService: ToastService
  ) {
    super()
  }

  addComment() {
    const comment: string = this.commentForm
      .get('newComment')
      .value.toString()
      .trim()
    if (comment.length == 0) {
      this.newCommentError = true
      return
    }
    this.newCommentError = false
    this.networkActive = true
    this.commentsService.addComment(this.documentId, comment).subscribe({
      next: (result) => {
        this.comments = result
        this.commentForm.get('newComment').reset()
        this.networkActive = false
        this.updated.emit(this.comments)
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
        this.updated.emit(this.comments)
      },
      error: (e) => {
        this.networkActive = false
        this.toastService.showError(
          $localize`Error deleting comment: ${e.toString()}`
        )
      },
    })
  }

  displayName(comment: PaperlessDocumentComment): string {
    if (!comment.user) return ''
    let nameComponents = []
    if (comment.user.first_name) nameComponents.unshift(comment.user.first_name)
    if (comment.user.last_name) nameComponents.unshift(comment.user.last_name)
    if (comment.user.username) {
      if (nameComponents.length > 0)
        nameComponents.push(`(${comment.user.username})`)
      else nameComponents.push(comment.user.username)
    }
    return nameComponents.join(' ')
  }

  commentFormKeydown(event: KeyboardEvent) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      this.addComment()
    }
  }
}
