import { ObjectWithId } from './object-with-id'
import { PaperlessCorrespondent } from './paperless-correspondent'
import { PaperlessDocumentType } from './paperless-document-type'
import { PaperlessMailAccount } from './paperless-mail-account'
import { PaperlessTag } from './paperless-tag'

export enum MailFilterAttachmentType {
  Attachments = 1,
  Everything = 2,
}

export enum MailAction {
  Delete = 1,
  Move = 2,
  MarkRead = 3,
  Flag = 4,
  Tag = 5,
}

export enum MailMetadataTitleOption {
  FromSubject = 1,
  FromFilename = 2,
}

export enum MailMetadataCorrespondentOption {
  FromNothing = 1,
  FromEmail = 2,
  FromName = 3,
  FromCustom = 4,
}

export interface PaperlessMailRule extends ObjectWithId {
  name: string

  order: number

  account: PaperlessMailAccount

  folder: string

  filter_from: string

  filter_subject: string

  filter_body: string

  filter_attachment_filename: string

  maximum_age: number

  attachment_type: MailFilterAttachmentType

  action: MailAction

  action_parameter?: string

  assign_title_from: MailMetadataTitleOption

  assign_tags?: PaperlessTag[]

  assign_document_type?: PaperlessDocumentType

  assign_correspondent_from?: MailMetadataCorrespondentOption

  assign_correspondent?: PaperlessCorrespondent
}
