import "./Button.scss"
import Button from 'react-bootstrap/Button';

const ButtonComponent = (props) => {
    return (
        <Button href={props.href} type={props.type} variant={props.variant} className={props.style} size={props.size}>
            {props.text}
        </Button>
    )
}

export default ButtonComponent;