import "./Button.scss"
import Button from 'react-bootstrap/Button';

const Botão = (props) =>{
    return (
        
     
        <Button href={props.href} variant={props.variant} className={props.style}  size={props.size}>
          {props.text}
        </Button>
     
    )
}

export default Botão;