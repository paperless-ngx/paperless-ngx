import { DocumentTitlePipe } from './document-title.pipe'

describe('DocumentTitlePipe', () => {
  it('should return a value if not null', () => {
    const pipe = new DocumentTitlePipe()
    expect(pipe.transform('some string')).toEqual('some string')
    expect(pipe.transform(null)).toEqual('(no title)')
  })
})
